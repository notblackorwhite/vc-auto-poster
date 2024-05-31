# Votecount Auto-poster
Automatically post new votecounts periodically. Requires the Discourse
votecount plugin.

# Requirements
The host environment must have the following:
- Python >= 3.12

The [discourse-votecount](https://github.com/kcereru/discourse-votecount)
plugin must be installed and working on the Discourse site you configure.

# Installation
I haven't done a package install or anything yet, so it's just download the
project, install it, and run it. Below are step-by-step instructions that should
work on any POSIX compliant platform (Linux, MacOS probably, FreeBSD probably).
If you're trying to run it on Windows I would strongly recommend setting up WSL2
first, and doing it inside of WSL.

I would recommend using a `venv` until there's a true package install. Run while
inside the project directory:
```
python3.12 -m venv venv
```

Install it using `pip` (use an editable install if you want to tinker around):
```
pip install .
```
```
pip install --editable .
```

Copy `sample.vc-auto-poster.toml` to the `.config` directory of the user you
plan to run the bot with as `vc-auto-poster.toml`. If that's the current user:
```
cp -v sample.vc-auto-poster.toml ~/.config/vc-auto-poster.toml
```

Or some arbitrary user:
```
cp -v sample.vc-auto-poster.toml /home/someuser/.config/vc-auto-poster.toml
```

Configure all the required fields, and whatever else you want. The comments in
the config should make it pretty straightforward.

# Usage
Run it using the script in `bin/` or as a module. The `python` command needs to
point to an environment where the module is actually installed which is probably
the `venv`.

```
python -m vc_autoposter
```
```
./bin/vc-auto-poster
```

Once there's a package build it'll be simpler, but, uh, yeah that's what you do
right now.

The bot reads the data collated by the `discourse-votecount` plugin, and you
need to be using that plugin correctly for the bot to post accurate votecounts.

## Topic Tags
The bot can read topic tags, and it affects some of its behavior.

Any tag that's `day-X` where `X` is an integer will be used to add "Day X" to
the post heading. Requires `pretty` to be `true` in the configuration for a
heading to be posted. If there are multiple `day-X` tags, it will go with
whatever it finds first that matches that pattern.

The `suppress_tags` configuration parameter accepts a list of tags that will
suppress all output while the bot sees *any* of them in the topic tags.

## Vote Post Links
If `links` is `true` in the configuration, the bot will do its best to add a
link to the post the vote was made. It *mostly* relies on the
`discourse-votecount` plugin for this, but 

# Authors
- notblackorwhite