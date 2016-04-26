py4chanbot
==============

Now you can take the shitposting with you to IRC!

The bot was designed to act as a live feed from a 'general', or recurring thread, to an IRC channel. With a ~~little~~ fair bit more work on modularization and cleanups, it might be useful in other scenarios too.

py4chanbot utilizes the [BASC-py4chan](https://github.com/bibanon/BASC-py4chan) library to interact with [4chan's API](https://github.com/4chan/4chan-API) and the [irc](https://github.com/jaraco/irc) library for all IRC functionality. Only Python 3 is supported for now.

All code is released under [the MIT license](LICENSE).

### Installation
Since the latest BASC-py4chan release is currently missing some needed attributes, you'll need to fetch a newer version from their git repository. pip will handle this if you don't want to install dependencies manually.

```
pip install -r requirements.txt
python setup.py install
```

### Usage
Edit __config.cfg.example__ to your liking and save it as __config.cfg__, then simply run __4chanbot.py__.
