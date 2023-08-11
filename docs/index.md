# py2winapp

Make runnable apps from your python scripts!

## Description

### How it works

This script performs the following actions:

- Copies your source files to the build folder
- Downloads Python interpreter to the build folder
- Installs `pip`
- Installs your project's requirements
- Makes an executable startup file wich runs your main script

You'll get a portable Windows application!

### Requirements and limitations

- Python 3.9+
- Tested on Windows 10 only
- Now only `x64` architecture is supported.

## Installation

With `pip`:

```sh
pip install py2winapp
```

With `poetry`:

```bash
poetry add py2winapp --group dev
```

## License

MIT

## Credits

- inspired by [ClimenteA/pyvan](https://github.com/ClimenteA/pyvan#readme)
- used code from [silvandeleemput/gen-exe](https://github.com/silvandeleemput/gen-exe)
