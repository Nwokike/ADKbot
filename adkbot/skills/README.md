# adkbot Skills

This directory contains built-in skills that extend adkbot's capabilities.

## Skill Format

Each skill is a directory containing a `SKILL.md` file with:
- YAML frontmatter (name, description, metadata)
- Markdown instructions for the agent

## Skill Registry

adkbot integrates with [ClawHub](https://clawhub.ai), the public skill registry for AI agents.
You can search, install, and update skills from ClawHub directly through the agent:

```bash
# Search for skills
npx --yes clawhub@latest search "web scraping" --limit 5

# Install a skill
npx --yes clawhub@latest install <slug> --workdir ~/.adkbot/workspace
```

## Available Skills

| Skill | Description |
|-------|-------------|
| `clawhub` | Search and install skills from the ClawHub public registry |
| `github` | Interact with GitHub using the `gh` CLI |
| `weather` | Get weather info using wttr.in and Open-Meteo |
| `summarize` | Summarize URLs, files, and YouTube videos |
| `tmux` | Remote-control tmux sessions |
| `skill-creator` | Create new skills |