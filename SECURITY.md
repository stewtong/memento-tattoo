<!-- register: public security policy | reader: someone who found a possible vulnerability | consumed: read once before reporting -->

# Security policy

## Reporting a vulnerability

Report a suspected vulnerability privately through GitHub: open the repository's **Security** tab and choose **Report a vulnerability**, or go to [the private report form](https://github.com/stewtong/memento-tattoo/security/advisories/new). Please do not open a public issue or discussion for it.

A useful report includes the package version (`memento-tattoo --version`), the Python version and operating system, the command you ran, and a small synthetic memory root that reproduces the problem. Leave real notes, credentials and other private data out of the report.

This project has one maintainer, and reports are handled on a best-effort basis with no guaranteed response time. You will get a reply in the private advisory thread, and a confirmed issue is fixed and disclosed through a GitHub security advisory. Reporters are credited in the advisory unless they ask not to be.

## Supported versions

Fixes land on `main` and ship in the next release. Only the latest release receives security fixes.

## What the package does

`memento-tattoo` is a local command-line tool with no runtime dependencies. It reads and writes Markdown and JSONL files under a memory root and a project directory that you choose. It makes no network requests, calls no model, and starts no background process.

## In scope

- A command that reads, writes, moves or deletes a file outside the memory root or project directory it was given, including through a symbolic link or a crafted path in a note, session ID or spec file.
- A crafted memory file, save spec or registry line that makes the tool run code or commands.
- A lock or write-check bypass that silently loses or overwrites another writer's data.
- The public export script (`scripts/export_public.py`) copying a file outside its published list.

## Out of scope

- **Instructions inside memory files.** Notes, tattoos and `memory.md` are loaded into an agent's context, so anyone who can edit them can give the agent instructions. That is the purpose of the files. Treat changes to them like changes to `AGENTS.md` or `CLAUDE.md`, and review them before merging.
- **Secrets written into notes.** The files are plain text in your repository. Do not store credentials in them.
- **What an agent does with a lesson.** The agent and its harness decide how to act on what memento returns.
