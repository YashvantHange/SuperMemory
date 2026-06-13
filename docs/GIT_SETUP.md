# Git author identity

Commits must use **your** name and a **verified GitHub email** so they appear on your profile with your avatar.

## Fix on your machine (one time)

In PowerShell or CMD:

```bash
git config --global user.name "Yashvant Hange"
git config --global user.email "yashvanthange420@gmail.com"
```

Verify:

```bash
git config --global user.name
git config --global user.email
```

**Important:** The email must match an address added under  
GitHub → **Settings → Emails** (and be verified).

Alternative — GitHub private noreply address:

```bash
git config --global user.email "YashvantHange@users.noreply.github.com"
```

## Why past commits looked wrong

Earlier commits used:

- Name: `yashvanthange` (lowercase handle, not display name)
- Email: `yashvanthange420@gmail.com.com` (typo — extra `.com`)

GitHub could not link those commits to [@YashvantHange](https://github.com/YashvantHange), so they showed as an unlinked contributor.

The repo includes `.mailmap` so GitHub displays the correct name for those commits. New commits after fixing `git config` will link to your profile automatically.

## Cursor / AI commits

When Cursor commits on your machine, it uses **your local `git config`** as author.  
But Cursor also adds this line to the commit message:

```
Co-authored-by: Cursor <cursoragent@cursor.com>
```

GitHub then shows **cursoragent** as a second committer (`yashvanthange` + `cursoragent`).

### Stop it (recommended)

1. Open **Cursor Settings → Agents → Attribution**
2. Turn **off Commit Attribution** (and PR Attribution if you prefer)

For Cursor CLI, add to `%USERPROFILE%\.cursor\cli-config.json`:

```json
{
  "attribution": {
    "attributeCommitsToAgent": false,
    "attributePRsToAgent": false
  }
}
```

### Repo hook (backup)

If attribution still appears, install the local hook:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_git_hooks.ps1
```

This removes `cursoragent@cursor.com` lines before each commit is finalized.

### Fix an already-pushed commit

Only if you are OK rewriting history on `main`:

```bash
git commit --amend -m "Your message without the Co-authored-by line"
git push --force-with-lease
```

For many commits, use interactive rebase or ask for help — do not force-push shared branches without coordinating.
