# CHANGELOG


## Unreleased

### Bug Fixes

- **repo**: Made full repo ty compliant
  ([`2504b19`](https://github.com/dagl1/VmaxBuilder/commit/2504b197cdc564a2dcbd03c8e6c35a7322bedbec))

### Continuous Integration

- **CI**: Now includes pytest
  ([`46a957f`](https://github.com/dagl1/VmaxBuilder/commit/46a957fad63e51f00462949d79c4856622c227f9))

- **ci.yaml**: Additional fix for not getting errors in tests CI
  ([`1818e6c`](https://github.com/dagl1/VmaxBuilder/commit/1818e6ccad85f9b0c627ee0c217e08f3039ddf0e))

- **ci.yml**: Allowed for exit code if specific test does not (yet) exist
  ([`6b4b861`](https://github.com/dagl1/VmaxBuilder/commit/6b4b861a6cd12752a8eee4368bf40579951cd355))

- **CI.yml**: Changed from uvx to uv run such that we use pyproject settings
  ([`f5edaaa`](https://github.com/dagl1/VmaxBuilder/commit/f5edaaa23d4a9605e75eb24a85e87ffce7611909))

- **CI.yml**: Fixed indendation
  ([`bc8a796`](https://github.com/dagl1/VmaxBuilder/commit/bc8a79603e4ffa9bc70afd360856427586c0fc0c))

- **ci.yml**: Removed mypy
  ([`46d56cc`](https://github.com/dagl1/VmaxBuilder/commit/46d56cc3c6727c50e69ab7b2ff553d0038a03c50))

- **tests-for-ci**: Added test marks for different types (unit, integration, usability)
  ([`495b48e`](https://github.com/dagl1/VmaxBuilder/commit/495b48e7c8332e91a5f1223b6191a620b79c4613))

### Documentation

- **docs**: Landing page
  ([`a14ede6`](https://github.com/dagl1/VmaxBuilder/commit/a14ede6d39773f63364f8da84bfd014f11688ccf))

- **docs-&-sphinx-confix**: Fixed version in init, and conf.py package loading for read-the-docs
  ([`15bbf60`](https://github.com/dagl1/VmaxBuilder/commit/15bbf60fcec189d3ce173df46f3ea7e08cdc0c61))

- **readme**: Updated links to CI and docs
  ([`f6f7cf2`](https://github.com/dagl1/VmaxBuilder/commit/f6f7cf2daf539f79e296b815dfc450dc864c8db3))

- **refactor-documentaiton**: Added overview of API layout and rules
  ([`c1715c3`](https://github.com/dagl1/VmaxBuilder/commit/c1715c3ae3fa1d100b0c852244f119cba5b97d14))

### Refactoring

- **repo**: Replaced SWAMP with VmaxBuilder throughout repo
  ([`63aa6fe`](https://github.com/dagl1/VmaxBuilder/commit/63aa6fe1a10f584258a66ed44edf21d61dbac05d))

### Testing

- **add_large_files_to_gitignore.py**: Added complexity ignore
  ([`83a8404`](https://github.com/dagl1/VmaxBuilder/commit/83a8404c8501f380fcc46e22e832e7bf324143e2))


## v0.1.0 (2026-05-20)

### Build System

- **pyproject**: Uses updated pandas-stubs
  ([`aff0ba4`](https://github.com/dagl1/VmaxBuilder/commit/aff0ba4ae9230eca0506f18bdcbcb62628be41b7))

### Code Style

- **custom_logging**: Removed typing issues with Logger
  ([`2d9dc78`](https://github.com/dagl1/VmaxBuilder/commit/2d9dc785643a6c2fb9694625db4a202655653a64))

### Documentation

- **API,-agent-instructions**: Created full refactor plan, new architecture, added API endpoints
  ([`929890e`](https://github.com/dagl1/VmaxBuilder/commit/929890ec1ca51962cac037c1de1bd42705fca065))

### Features

- **repo-structure**: Initial dev commit for transfer, includes new repo structure and template
  files for refac
  ([`55e4cfe`](https://github.com/dagl1/VmaxBuilder/commit/55e4cfe8e1888376ed38ebace077496fd7255a9e))

### Refactoring

- **repo-VmaxBuilder**: Restructured data
  ([`53cc5d7`](https://github.com/dagl1/VmaxBuilder/commit/53cc5d76ededa45edfdb34da96ca20a4a363c98c))

- **src**: Restructured directory organization based on new API setup
  ([`99e16c6`](https://github.com/dagl1/VmaxBuilder/commit/99e16c6aca6f7d1f8aea072c6d5f8ee7f575cee2))

- **utils**: Made pathlib and ty/ruff compliant
  ([`478e4a8`](https://github.com/dagl1/VmaxBuilder/commit/478e4a8eabd94e247931934786da106eec2accd5))

### Testing

- **cobrapy_overwrites**: Now includes tests for checking new overwrites
  ([`5cd92d3`](https://github.com/dagl1/VmaxBuilder/commit/5cd92d33207fa316f2a8b206be7907876084a89d))

- **utils**: Included tests for utils folder
  ([`b9997b8`](https://github.com/dagl1/VmaxBuilder/commit/b9997b8a4761240ec476a5fcc737f747166ccf75))
