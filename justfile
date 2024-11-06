# pgai python library. List recipes with `just -l pgai`
mod pgai 'projects/pgai/justfile'
# pgai postgres extension. List recipes with `just -l ext`
mod ext 'projects/extension/justfile'

# Show list of recipes
default:
    @just --list
    @echo "\nproject/pgai recipes: just pgai [recipe]\n"
    @just --list pgai
    @echo "\nproject/extension recipes: just ext [recipe]\n"
    @just --list ext

ci:
  just pgai ci
  just ext ci

# Install semantic commit message hook
install-commit-hook:
  @cd ../.. && curl --fail -o .git/hooks/commit-msg https://raw.githubusercontent.com/hazcod/semantic-commit-hook/master/commit-msg \
  && chmod 500 .git/hooks/commit-msg
