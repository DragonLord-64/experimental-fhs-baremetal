# Setup Apt source

Configures an APT source and sends its HTTP traffic through the internal
apt-cacher-ng service.

## Variables

| Var | Default | Purpose |
|---|---|---|
| `apt_repo_url` | `""` | APT repository URL |
| `apt_repo_url_base` | `""` | Base portion of the repository URL |
| `apt_repo_host_name` | `""` | Repository hostname |
| `apt_repo_release` | `{{ ansible_distribution_release }}` | Suite name (codename) |
| `apt_repo_components` | `[main, universe]` | Components to enable |
| `apt_repo_suites` | `[noble, noble-updates, ...]` | List of suites to include in sources |
| `apt_cache_url` | `""` | apt-cacher-ng URL, including its port |
| `apt_repo_keyring` | `/usr/share/keyrings/ubuntu-archive-keyring.gpg` | Ubuntu archive keyring used by `Signed-By` |
| `apt_repo_name` | `fhs` | Name used for file naming |
| `apt_repo_sources_file` | `/etc/apt/sources.list.d/fhs.sources` | deb822 file path |
| `apt_repo_conf_dir` | `/etc/apt/apt.conf.d/` | Directory for apt proxy configurations |
| `apt_repo_run_update` | `true` | Whether to run `apt update` after configuration |

Packages retrieved through apt-cacher-ng retain Ubuntu's original signatures
and are verified against the keyring supplied by the `ubuntu-keyring` package.

Tags: `apt_repo`, `config`.
