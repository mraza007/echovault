use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Cell, Clear, List, ListItem, Paragraph, Row, Table, Wrap},
    Frame,
};

use crate::app::{App, InputMode, Mode};

const ACCENT: Color = Color::Rgb(254, 166, 43);
const DIM: Color = Color::DarkGray;

pub fn draw(f: &mut Frame, app: &App) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(1), // header
            Constraint::Min(1),   // body
            Constraint::Length(1), // footer
        ])
        .split(f.area());

    draw_header(f, app, chunks[0]);
    draw_footer(f, app, chunks[2]);

    match app.mode {
        Mode::Overview => draw_overview(f, app, chunks[1]),
        Mode::Memories => draw_memories(f, app, chunks[1]),
        Mode::Review => draw_review(f, app, chunks[1]),
        Mode::Operations => draw_operations(f, app, chunks[1]),
    }

    if app.show_help {
        draw_help(f, f.area());
    }
    if app.show_confirm {
        draw_confirm(f, app, f.area());
    }
    if let Some(ref notif) = app.notification {
        draw_notification(f, notif, f.area());
    }
}

fn draw_header(f: &mut Frame, app: &App, area: Rect) {
    let mode_str = match app.mode {
        Mode::Overview => ":overview",
        Mode::Memories => ":memories",
        Mode::Review => ":review",
        Mode::Operations => ":ops",
    };
    let project = if app.project_filter.is_empty() {
        "all projects"
    } else {
        &app.project_filter
    };
    let count = match app.mode {
        Mode::Memories => app.memories.len().to_string(),
        _ => app.stats_total.to_string(),
    };

    let header = Line::from(vec![
        Span::styled(" EchoVault ", Style::default().fg(Color::Black).bg(ACCENT).add_modifier(Modifier::BOLD)),
        Span::styled(format!(" {} ", mode_str), Style::default().fg(Color::White).bg(ACCENT)),
        Span::styled(
            " ".repeat((area.width as usize).saturating_sub(14 + mode_str.len() + project.len() + count.len() + 12).max(1)),
            Style::default().bg(ACCENT),
        ),
        Span::styled(format!(" {} ", project), Style::default().fg(Color::White).bg(ACCENT)),
        Span::styled(format!(" {} memories ", count), Style::default().fg(Color::White).bg(ACCENT)),
    ]);
    f.render_widget(Paragraph::new(header), area);
}

fn draw_footer(f: &mut Frame, app: &App, area: Rect) {
    let hints = match app.input_mode {
        InputMode::Search => "Type to search | Esc exit search | Enter apply",
        InputMode::Command => &format!(": {}", app.input_buffer),
        InputMode::Normal => match app.mode {
            Mode::Overview => "1 Overview  2 Memories  3 Review  4 Ops  r Refresh  : Command  q Quit",
            Mode::Memories => "j/k Nav  e Edit  n New  a Archive  / Search  : Cmd  q Quit",
            Mode::Review => "j/k Nav  m Merge(R>L)  a Archive Right  x Keep Sep  : Cmd  q Quit",
            Mode::Operations => "r Refresh  : Command  q Quit",
        },
    };
    let footer = Paragraph::new(Line::from(Span::styled(
        format!(" {}", hints),
        Style::default().fg(DIM),
    )))
    .style(Style::default().bg(Color::Rgb(30, 30, 30)));
    f.render_widget(footer, area);
}

fn draw_overview(f: &mut Frame, app: &App, area: Rect) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .margin(1)
        .split(area);

    let top = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(40), Constraint::Percentage(60)])
        .split(rows[0]);

    let bottom = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(40), Constraint::Percentage(60)])
        .split(rows[1]);

    // Memories stats
    let stats_text = vec![
        Line::from(format!("  Total     {}", app.stats_total)),
        Line::from(format!("  Active    {}", app.stats_active)),
        Line::from(format!("  Archived  {}", app.stats_archived)),
    ];
    let stats = Paragraph::new(stats_text)
        .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(ACCENT)).title(Span::styled(" Memories ", Style::default().fg(ACCENT).add_modifier(Modifier::BOLD))));
    f.render_widget(stats, top[0]);

    // Categories
    let max_count = app.stats_categories.iter().map(|(_, c)| *c).max().unwrap_or(1);
    let cat_lines: Vec<Line> = app
        .stats_categories
        .iter()
        .take(8)
        .map(|(name, count)| {
            let bar_w = if max_count > 0 {
                (*count as usize * 20) / max_count as usize
            } else {
                0
            };
            let bar = "#".repeat(bar_w) + &".".repeat(20 - bar_w);
            Line::from(format!("  {:<12} [{}] {:>4}", &name[..name.len().min(12)], bar, count))
        })
        .collect();
    let cats = Paragraph::new(cat_lines)
        .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(ACCENT)).title(Span::styled(" Categories ", Style::default().fg(ACCENT).add_modifier(Modifier::BOLD))));
    f.render_widget(cats, top[1]);

    // Projects
    let proj_lines: Vec<Line> = app
        .stats_projects
        .iter()
        .take(10)
        .map(|(name, count)| Line::from(format!("  {:<28} {:>4}", &name[..name.len().min(28)], count)))
        .collect();
    let projects = Paragraph::new(proj_lines)
        .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(ACCENT)).title(Span::styled(" Projects ", Style::default().fg(ACCENT).add_modifier(Modifier::BOLD))));
    f.render_widget(projects, bottom[0]);

    // Recent
    let recent_lines: Vec<Line> = app
        .stats_recent
        .iter()
        .take(8)
        .map(|m| {
            Line::from(format!(
                "  {:<44} {}",
                &m.title[..m.title.len().min(44)],
                &m.updated_at[..m.updated_at.len().min(10)]
            ))
        })
        .collect();
    let recent = Paragraph::new(recent_lines)
        .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(ACCENT)).title(Span::styled(" Recent ", Style::default().fg(ACCENT).add_modifier(Modifier::BOLD))));
    f.render_widget(recent, bottom[1]);
}

fn draw_memories(f: &mut Frame, app: &App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // filter bar
            Constraint::Length(1), // summary
            Constraint::Percentage(55), // table
            Constraint::Min(5),   // detail
        ])
        .split(area);

    // Filter bar
    let filter_text = match app.input_mode {
        InputMode::Search => format!(
            " Search: {}_ | Project: {} | Category: {} | Archived: {}",
            app.input_buffer,
            if app.project_filter.is_empty() { "all" } else { &app.project_filter },
            if app.category_filter.is_empty() { "all" } else { &app.category_filter },
            if app.include_archived { "yes" } else { "no" },
        ),
        _ => format!(
            " Search: {} | Project: {} | Category: {} | Archived: {}",
            if app.search_query.is_empty() { "(press /)" } else { &app.search_query },
            if app.project_filter.is_empty() { "all" } else { &app.project_filter },
            if app.category_filter.is_empty() { "all" } else { &app.category_filter },
            if app.include_archived { "yes" } else { "no" },
        ),
    };
    let filter = Paragraph::new(filter_text)
        .block(Block::default().borders(Borders::BOTTOM).border_style(Style::default().fg(DIM)));
    f.render_widget(filter, chunks[0]);

    // Summary
    let summary = Paragraph::new(Line::from(Span::styled(
        format!(" {} memories", app.memories.len()),
        Style::default().fg(DIM),
    )));
    f.render_widget(summary, chunks[1]);

    // Table
    let selected_style = Style::default().bg(Color::Rgb(50, 50, 80)).add_modifier(Modifier::BOLD);
    let header = Row::new(vec![
        Cell::from("Title"),
        Cell::from("Project"),
        Cell::from("Category"),
        Cell::from("Status"),
        Cell::from("Updated"),
    ])
    .style(Style::default().fg(ACCENT).add_modifier(Modifier::BOLD))
    .bottom_margin(0);

    let rows: Vec<Row> = app
        .memories
        .iter()
        .enumerate()
        .map(|(i, m)| {
            let style = if i == app.memory_selected {
                selected_style
            } else if i % 2 == 0 {
                Style::default()
            } else {
                Style::default().bg(Color::Rgb(22, 22, 22))
            };
            Row::new(vec![
                Cell::from(m.title.clone()),
                Cell::from(m.project.clone()),
                Cell::from(m.category.clone().unwrap_or_default()),
                Cell::from(m.status.clone().unwrap_or_else(|| "active".to_string())),
                Cell::from(m.updated_at[..m.updated_at.len().min(10)].to_string()),
            ])
            .style(style)
        })
        .collect();

    let table = Table::new(
        rows,
        [
            Constraint::Percentage(40),
            Constraint::Percentage(15),
            Constraint::Percentage(12),
            Constraint::Percentage(8),
            Constraint::Percentage(12),
        ],
    )
    .header(header)
    .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(DIM)));
    f.render_widget(table, chunks[2]);

    // Detail panel
    let detail_block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(ACCENT));

    if let Some(ref mem) = app.memory_detail {
        let mut lines = vec![
            Line::from(vec![
                Span::styled(&mem.title, Style::default().fg(ACCENT).add_modifier(Modifier::BOLD)),
                Span::styled(
                    format!("  |  {}  |  {}", mem.category.as_deref().unwrap_or("uncategorized"), &mem.project),
                    Style::default().fg(DIM),
                ),
            ]),
            Line::from(""),
        ];
        lines.push(Line::from(format!("What: {}", mem.what)));
        if let Some(ref why) = mem.why {
            lines.push(Line::from(format!("Why:  {}", why)));
        }
        if let Some(ref impact) = mem.impact {
            lines.push(Line::from(format!("Impact: {}", impact)));
        }
        let tags = crate::db::format_tags(&mem.tags);
        if !tags.is_empty() {
            lines.push(Line::from(format!("Tags: {}", tags)));
        }
        if let Some(ref details) = mem.details {
            lines.push(Line::from(""));
            for line in details.lines() {
                lines.push(Line::from(line.to_string()));
            }
        }
        let detail = Paragraph::new(lines).block(detail_block).wrap(Wrap { trim: false });
        f.render_widget(detail, chunks[3]);
    } else {
        let detail = Paragraph::new("Select a memory to preview.").block(detail_block);
        f.render_widget(detail, chunks[3]);
    }
}

fn draw_review(f: &mut Frame, app: &App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(40), Constraint::Percentage(60)])
        .split(area);

    // Duplicate table
    let selected_style = Style::default().bg(Color::Rgb(50, 50, 80)).add_modifier(Modifier::BOLD);
    let header = Row::new(vec![
        Cell::from("Left"),
        Cell::from("Right"),
        Cell::from("Project"),
        Cell::from("Score"),
    ])
    .style(Style::default().fg(ACCENT).add_modifier(Modifier::BOLD));

    let rows: Vec<Row> = if app.duplicate_loading {
        vec![Row::new(vec![Cell::from("Loading duplicates...")])]
    } else {
        app.duplicates
            .iter()
            .enumerate()
            .map(|(i, p)| {
                let style = if i == app.duplicate_selected {
                    selected_style
                } else if i % 2 == 0 {
                    Style::default()
                } else {
                    Style::default().bg(Color::Rgb(22, 22, 22))
                };
                Row::new(vec![
                    Cell::from(p.left_title.clone()),
                    Cell::from(p.right_title.clone()),
                    Cell::from(p.project.clone()),
                    Cell::from(format!("{:.2}", p.score)),
                ])
                .style(style)
            })
            .collect()
    };

    let table = Table::new(
        rows,
        [
            Constraint::Percentage(35),
            Constraint::Percentage(35),
            Constraint::Percentage(20),
            Constraint::Percentage(10),
        ],
    )
    .header(header)
    .block(Block::default().borders(Borders::ALL).border_style(Style::default().fg(DIM)));
    f.render_widget(table, chunks[0]);

    // Side-by-side comparison
    let compare = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)])
        .split(chunks[1]);

    if let Some(pair) = app.duplicates.get(app.duplicate_selected) {
        let left = Paragraph::new(vec![
            Line::from(""),
            Line::from(pair.left_what.clone()),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(ACCENT))
                .title(Span::styled(
                    format!(" LEFT: {} ", pair.left_title),
                    Style::default().fg(ACCENT).add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
        f.render_widget(left, compare[0]);

        let right = Paragraph::new(vec![
            Line::from(""),
            Line::from(pair.right_what.clone()),
        ])
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(ACCENT))
                .title(Span::styled(
                    format!(" RIGHT: {} ", pair.right_title),
                    Style::default().fg(ACCENT).add_modifier(Modifier::BOLD),
                )),
        )
        .wrap(Wrap { trim: false });
        f.render_widget(right, compare[1]);
    } else {
        let msg = if app.duplicate_loading {
            "Loading..."
        } else {
            "No duplicate candidates."
        };
        let left = Paragraph::new(msg).block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(ACCENT))
                .title(" LEFT "),
        );
        let right = Paragraph::new("").block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(Style::default().fg(ACCENT))
                .title(" RIGHT "),
        );
        f.render_widget(left, compare[0]);
        f.render_widget(right, compare[1]);
    }
}

fn draw_operations(f: &mut Frame, app: &App, area: Rect) {
    let chunks = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(5), Constraint::Min(3)])
        .margin(1)
        .split(area);

    let actions = Paragraph::new(vec![
        Line::from(""),
        Line::from("  Operations are available via the Python CLI:"),
        Line::from("  memory import | memory reindex | memory dashboard --help"),
    ])
    .block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(ACCENT))
            .title(Span::styled(
                " Actions ",
                Style::default().fg(ACCENT).add_modifier(Modifier::BOLD),
            )),
    );
    f.render_widget(actions, chunks[0]);

    let log_items: Vec<ListItem> = app
        .op_log
        .iter()
        .map(|l| ListItem::new(Line::from(l.as_str())))
        .collect();
    let log = List::new(log_items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(DIM))
            .title(Span::styled(
                " Log ",
                Style::default().fg(ACCENT).add_modifier(Modifier::BOLD),
            )),
    );
    f.render_widget(log, chunks[1]);
}

fn draw_help(f: &mut Frame, area: Rect) {
    let help_text = r#"
  EchoVault Dashboard

  Navigation
    1 2 3 4    Switch: Overview / Memories / Review / Ops
    :          Command palette
    ?          This help
    q          Quit

  Memories
    j / k      Navigate rows
    g / G      Jump to first / last row
    /          Search
    e          Edit selected in $EDITOR
    n          New memory in $EDITOR
    a          Archive / restore selected

  Review Queue
    j / k      Navigate pairs
    m          Merge right into left
    a          Archive right
    x          Keep separate

  Commands (via :)
    :overview  :memories  :review  :ops
    :project <name>       :refresh  :q

  Press Esc or ? to close
"#;
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(ACCENT))
        .title(" Help ");
    let popup_area = centered_rect(60, 80, area);
    f.render_widget(Clear, popup_area);
    let help = Paragraph::new(help_text)
        .block(block)
        .style(Style::default().bg(Color::Rgb(25, 25, 25)));
    f.render_widget(help, popup_area);
}

fn draw_confirm(f: &mut Frame, app: &App, area: Rect) {
    let popup_area = centered_rect(50, 20, area);
    f.render_widget(Clear, popup_area);
    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(ACCENT));
    let text = vec![
        Line::from(""),
        Line::from(app.confirm_message.clone()),
        Line::from(""),
        Line::from(Span::styled(
            "  [y] Confirm    [n] Cancel",
            Style::default().fg(DIM),
        )),
    ];
    let confirm = Paragraph::new(text)
        .block(block)
        .style(Style::default().bg(Color::Rgb(25, 25, 25)));
    f.render_widget(confirm, popup_area);
}

fn draw_notification(f: &mut Frame, msg: &str, area: Rect) {
    let width = (msg.len() + 4).min(area.width as usize);
    let x = area.width.saturating_sub(width as u16) - 1;
    let notif_area = Rect::new(x, area.height - 3, width as u16, 1);
    let notif = Paragraph::new(Span::styled(
        format!(" {} ", msg),
        Style::default().fg(Color::Black).bg(ACCENT),
    ));
    f.render_widget(notif, notif_area);
}

fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let popup_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Percentage((100 - percent_y) / 2),
            Constraint::Percentage(percent_y),
            Constraint::Percentage((100 - percent_y) / 2),
        ])
        .split(r);
    Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Percentage((100 - percent_x) / 2),
            Constraint::Percentage(percent_x),
            Constraint::Percentage((100 - percent_x) / 2),
        ])
        .split(popup_layout[1])[1]
}
