mod app;
mod db;
mod duplicate;
mod editor;
mod ui;

use app::{App, InputMode, Mode};
use clap::Parser;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};
use std::io;
use std::path::PathBuf;
use std::time::Duration;

#[derive(Parser)]
#[command(name = "memory-dashboard", about = "EchoVault terminal dashboard")]
struct Cli {
    /// Initial project filter
    #[arg(long)]
    project: Option<String>,

    /// Show archived memories
    #[arg(long)]
    include_archived: bool,

    /// Path to memory home directory
    #[arg(long, env = "MEMORY_HOME")]
    memory_home: Option<String>,
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Write panics to a log file so we can debug TUI crashes
    std::panic::set_hook(Box::new(|info| {
        let _ = disable_raw_mode();
        let _ = execute!(io::stdout(), LeaveAlternateScreen, DisableMouseCapture);
        eprintln!("Dashboard panicked: {}", info);
    }));

    let cli = Cli::parse();

    let memory_home = cli
        .memory_home
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home).join(".memory")
        });

    let db_path = memory_home.join("index.db");
    if !db_path.exists() {
        eprintln!("Database not found at {:?}. Run `memory init` first.", db_path);
        std::process::exit(1);
    }

    let database = db::Db::open(&db_path).map_err(|e| {
        eprintln!("Failed to open database: {}", e);
        e
    })?;
    let mut app = App::new(
        database,
        db_path,
        cli.project.unwrap_or_default(),
        cli.include_archived,
    );
    app.refresh_overview();

    // Setup terminal
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;

    let result = run_app(&mut terminal, &mut app);

    // Restore terminal
    disable_raw_mode()?;
    execute!(
        terminal.backend_mut(),
        LeaveAlternateScreen,
        DisableMouseCapture
    )?;
    terminal.show_cursor()?;

    if let Err(err) = result {
        eprintln!("Error: {}", err);
    }
    Ok(())
}

fn run_app(
    terminal: &mut Terminal<CrosstermBackend<io::Stdout>>,
    app: &mut App,
) -> io::Result<()> {
    loop {
        terminal.draw(|f| ui::draw(f, app))?;

        // Poll with 100ms timeout for responsive UI + tick updates
        if event::poll(Duration::from_millis(100))? {
            if let Event::Key(key) = event::read()? {
                // Handle confirm dialog first
                if app.show_confirm {
                    match key.code {
                        KeyCode::Char('y') => app.execute_confirm(),
                        KeyCode::Char('n') | KeyCode::Esc => app.cancel_confirm(),
                        _ => {}
                    }
                    continue;
                }

                // Handle help overlay
                if app.show_help {
                    match key.code {
                        KeyCode::Esc | KeyCode::Char('?') | KeyCode::Char('q') => {
                            app.show_help = false;
                        }
                        _ => {}
                    }
                    continue;
                }

                // Handle search input mode
                if app.input_mode == InputMode::Search {
                    match key.code {
                        KeyCode::Esc => {
                            app.input_mode = InputMode::Normal;
                        }
                        KeyCode::Enter => {
                            app.search_query = app.input_buffer.clone();
                            app.input_mode = InputMode::Normal;
                            app.refresh_memories();
                        }
                        KeyCode::Backspace => {
                            app.input_buffer.pop();
                        }
                        KeyCode::Char(c) => {
                            app.input_buffer.push(c);
                        }
                        _ => {}
                    }
                    continue;
                }

                // Handle command input mode
                if app.input_mode == InputMode::Command {
                    match key.code {
                        KeyCode::Esc => {
                            app.input_buffer.clear();
                            app.input_mode = InputMode::Normal;
                        }
                        KeyCode::Enter => {
                            app.dispatch_command();
                        }
                        KeyCode::Backspace => {
                            app.input_buffer.pop();
                        }
                        KeyCode::Char(c) => {
                            app.input_buffer.push(c);
                        }
                        _ => {}
                    }
                    continue;
                }

                // Normal mode key handling
                if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
                    app.should_quit = true;
                }

                match key.code {
                    KeyCode::Char('q') => app.should_quit = true,
                    KeyCode::Char('1') => app.switch_mode(Mode::Overview),
                    KeyCode::Char('2') => app.switch_mode(Mode::Memories),
                    KeyCode::Char('3') => app.switch_mode(Mode::Review),
                    KeyCode::Char('4') => app.switch_mode(Mode::Operations),
                    KeyCode::Char('j') | KeyCode::Down => app.move_down(),
                    KeyCode::Char('k') | KeyCode::Up => app.move_up(),
                    KeyCode::Char('g') => app.move_top(),
                    KeyCode::Char('G') => app.move_bottom(),
                    KeyCode::Char('r') => {
                        app.refresh_current();
                        app.notify("Refreshed.");
                    }
                    KeyCode::Char('/') => {
                        app.input_mode = InputMode::Search;
                        app.input_buffer = app.search_query.clone();
                        if app.mode != Mode::Memories {
                            app.switch_mode(Mode::Memories);
                        }
                    }
                    KeyCode::Char(':') => {
                        app.input_mode = InputMode::Command;
                        app.input_buffer.clear();
                    }
                    KeyCode::Char('?') => {
                        app.show_help = true;
                    }
                    KeyCode::Char('e') if app.mode == Mode::Memories => {
                        // Suspend terminal for editor
                        disable_raw_mode()?;
                        execute!(
                            terminal.backend_mut(),
                            LeaveAlternateScreen,
                            DisableMouseCapture
                        )?;
                        terminal.show_cursor()?;

                        app.edit_selected();

                        // Restore terminal
                        enable_raw_mode()?;
                        execute!(
                            terminal.backend_mut(),
                            EnterAlternateScreen,
                            EnableMouseCapture
                        )?;
                        terminal.hide_cursor()?;
                        terminal.clear()?;
                    }
                    KeyCode::Char('n') => {
                        // Suspend terminal for editor
                        disable_raw_mode()?;
                        execute!(
                            terminal.backend_mut(),
                            LeaveAlternateScreen,
                            DisableMouseCapture
                        )?;
                        terminal.show_cursor()?;

                        app.new_memory();

                        // Restore terminal
                        enable_raw_mode()?;
                        execute!(
                            terminal.backend_mut(),
                            EnterAlternateScreen,
                            EnableMouseCapture
                        )?;
                        terminal.hide_cursor()?;
                        terminal.clear()?;
                    }
                    KeyCode::Char('a') => match app.mode {
                        Mode::Memories => app.archive_selected(),
                        Mode::Review => app.archive_duplicate_right(),
                        _ => {}
                    },
                    KeyCode::Char('m') if app.mode == Mode::Review => {
                        app.merge_selected();
                    }
                    KeyCode::Char('x') if app.mode == Mode::Review => {
                        app.keep_separate();
                    }
                    KeyCode::Esc => {
                        // Clear any active state
                    }
                    _ => {}
                }
            }
        }

        app.tick();

        if app.should_quit {
            return Ok(());
        }
    }
}
