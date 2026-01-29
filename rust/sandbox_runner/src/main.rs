use anyhow::{anyhow, Context, Result};
use clap::{Parser, Subcommand};
use regex::Regex;
use serde::Serialize;
use std::fs;
use std::io::{Read};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

#[derive(Parser, Debug)]
#[command(name = "sandbox_runner", version, about = "Best-effort sandboxed runner for untrusted evaluation.")]
struct Cli {
    /// Workspace root. All file operations are restricted to this directory.
    #[arg(long)]
    root: PathBuf,

    /// Wall time timeout in milliseconds.
    #[arg(long, default_value_t = 10000)]
    timeout_ms: u64,

    #[command(subcommand)]
    cmd: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Run an arbitrary command. Usage: sandbox_runner run -- <cmd> <args...>
    Run {
        #[arg(last = true, required = true)]
        argv: Vec<String>,
    },

    /// Convenience: run python -m pytest -q
    Pytest {},

    /// Read a file (path relative to root). Prints JSON with stdout=contents.
    ReadFile {
        #[arg(long)]
        path: String,
    },

    /// Apply a unified diff patch read from stdin. Uses git apply or patch.
    ApplyDiff {},
}

#[derive(Serialize)]
struct RunnerOutput {
    ok: bool,
    exit_code: i32,
    duration_s: f64,
    stdout: String,
    stderr: String,

    // optional metadata
    timed_out: bool,
    killed: bool,
    command: Vec<String>,
}

fn main() {
    let cli = Cli::parse();
    let out = match run(cli) {
        Ok(o) => o,
        Err(e) => RunnerOutput {
            ok: false,
            exit_code: 1,
            duration_s: 0.0,
            stdout: "".into(),
            stderr: format!("{:#}", e),
            timed_out: false,
            killed: false,
            command: vec![],
        },
    };

    // Always print JSON on stdout for machine parsing.
    println!("{}", serde_json::to_string(&out).unwrap());
}

fn canonicalize_root(root: &Path) -> Result<PathBuf> {
    let r = root
        .canonicalize()
        .with_context(|| format!("failed to canonicalize root: {}", root.display()))?;
    if !r.is_dir() {
        return Err(anyhow!("root is not a directory: {}", r.display()));
    }
    Ok(r)
}

fn ensure_within_root(root: &Path, rel: &str) -> Result<PathBuf> {
    if rel.contains('\0') {
        return Err(anyhow!("invalid path"));
    }
    let rel_path = Path::new(rel);

    // Disallow absolute paths
    if rel_path.is_absolute() {
        return Err(anyhow!("absolute paths are not allowed: {}", rel));
    }

    // Normalize and join
    let joined = root.join(rel_path);
    let canon = joined
        .canonicalize()
        .with_context(|| format!("failed to canonicalize path: {}", joined.display()))?;

    if !canon.starts_with(root) {
        return Err(anyhow!("path escapes root: {}", rel));
    }
    Ok(canon)
}

/// Validate that diff headers do not contain path traversal.
fn validate_patch_paths(patch: &str) -> Result<()> {
    // Parse lines like:
    // --- a/src/solution.py
    // +++ b/src/solution.py
    let re = Regex::new(r"^(---|\+\+\+)\s+([ab]/)?(?P<path>\S+)").unwrap();
    for line in patch.lines() {
        if let Some(caps) = re.captures(line) {
            let p = caps.name("path").unwrap().as_str();
            if p.starts_with('/') || p.contains("..") || p.contains('\\') {
                return Err(anyhow!("unsafe patch path in header: {}", p));
            }
        }
    }
    Ok(())
}

fn run(cli: Cli) -> Result<RunnerOutput> {
    let root = canonicalize_root(&cli.root)?;
    match cli.cmd {
        Commands::Run { argv } => {
            if argv.is_empty() {
                return Err(anyhow!("missing command argv"));
            }
            run_command(&root, cli.timeout_ms, &argv)
        }
        Commands::Pytest {} => {
            // Use python -m pytest -q
            run_command(&root, cli.timeout_ms, &vec!["python".into(), "-m".into(), "pytest".into(), "-q".into()])
        }
        Commands::ReadFile { path } => {
            let p = ensure_within_root(&root, &path)?;
            let bytes = fs::read(&p).with_context(|| format!("read failed: {}", p.display()))?;
            let s = String::from_utf8_lossy(&bytes).to_string();
            Ok(RunnerOutput {
                ok: true,
                exit_code: 0,
                duration_s: 0.0,
                stdout: s,
                stderr: "".into(),
                timed_out: false,
                killed: false,
                command: vec!["read-file".into(), path],
            })
        }
        Commands::ApplyDiff {} => {
            let mut patch = String::new();
            std::io::stdin().read_to_string(&mut patch)?;
            validate_patch_paths(&patch)?;

            // Write patch to a temp file inside root to avoid cross-dir references
            let patch_path = root.join(".tu_agent_patch.diff");
            fs::write(&patch_path, patch.as_bytes()).context("failed to write temp patch")?;

            // Try git apply first, then fall back to patch(1)
            let git_res = run_command(&root, cli.timeout_ms, &vec![
                "git".into(), "apply".into(),
                "--unsafe-paths".into(),
                "--whitespace=nowarn".into(),
                ".tu_agent_patch.diff".into()
            ]);

            let out = match git_res {
                Ok(o) if o.ok => o,
                _ => {
                    // patch -p1 < .tu_agent_patch.diff
                    // We'll run: patch -p1 -i .tu_agent_patch.diff
                    run_command(&root, cli.timeout_ms, &vec![
                        "patch".into(), "-p1".into(), "-i".into(), ".tu_agent_patch.diff".into()
                    ])?
                }
            };

            // Cleanup temp patch
            let _ = fs::remove_file(&patch_path);

            Ok(out)
        }
    }
}

fn run_command(root: &Path, timeout_ms: u64, argv: &Vec<String>) -> Result<RunnerOutput> {
    let start = Instant::now();
    let mut cmd = Command::new(&argv[0]);
    cmd.args(&argv[1..]);
    cmd.current_dir(root);
    cmd.stdin(Stdio::null());
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());

    // Best-effort environment minimization: keep PATH, and set PYTHONUNBUFFERED.
    // (Clearing env entirely can break some Python setups.)
    cmd.env("PYTHONUNBUFFERED", "1");

    // Unix resource limits (best effort)
    #[cfg(unix)]
    {
        use std::os::unix::process::CommandExt;
        cmd.pre_exec(move || {
            // CPU seconds, address space, open files
            set_rlimit(libc::RLIMIT_CPU, 2, 2)?;
            set_rlimit(libc::RLIMIT_NOFILE, 256, 256)?;
            // 512MB address space (best-effort, may be ignored on some OS)
            set_rlimit(libc::RLIMIT_AS, 512 * 1024 * 1024, 512 * 1024 * 1024)?;
            Ok(())
        });
    }

    let mut child = cmd.spawn().with_context(|| format!("failed to spawn: {:?}", argv))?;

    let timeout = Duration::from_millis(timeout_ms);
    let mut timed_out = false;
    let mut killed = false;

    loop {
        if start.elapsed() >= timeout {
            timed_out = true;
            // kill child
            let _ = child.kill();
            killed = true;
            break;
        }
        match child.try_wait()? {
            Some(_status) => break,
            None => std::thread::sleep(Duration::from_millis(10)),
        }
    }

    let output = child.wait_with_output()?;
    let duration_s = start.elapsed().as_secs_f64();
    let exit_code = output.status.code().unwrap_or(if output.status.success() { 0 } else { 1 });

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();

    Ok(RunnerOutput {
        ok: output.status.success() && !timed_out,
        exit_code,
        duration_s,
        stdout,
        stderr,
        timed_out,
        killed,
        command: argv.clone(),
    })
}

#[cfg(unix)]
fn set_rlimit(resource: libc::c_int, soft: u64, hard: u64) -> std::io::Result<()> {
    let lim = libc::rlimit {
        rlim_cur: soft as libc::rlim_t,
        rlim_max: hard as libc::rlim_t,
    };
    let res = unsafe { libc::setrlimit(resource, &lim as *const libc::rlimit) };
    if res != 0 {
        // If setrlimit fails, we don't hard error; we are "best effort".
        // Return Ok to avoid breaking environments without permission.
        return Ok(());
    }
    Ok(())
}
