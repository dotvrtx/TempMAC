# Tor Privacy Toolkit

A lightweight toolkit designed to improve privacy and anonymity when using the Tor network.

## Features

* Automatic Tor bridge injection
* Support for obfs4, Snowflake and Meek bridges
* Tor configuration backup and restoration
* Automatic Tor service restart
* Tor connection verification
* Real-time Tor leak monitoring
* Emergency network killswitch
* Detailed logging

## Requirements

### Python

* Python 3.8+

### Dependencies

Install required package:

```bash
pip install requests
```

### Tor

Tor must be installed and running.

#### Linux

```bash
sudo apt install tor
```


#### Windows

Install Tor Browser or Tor Expert Bundle.

---

## Installation

```bash
git clone https://github.com/dotvrtx/TempMAC.git
cd tor-privacy-toolkit
pip install requests
```

---

## Bridge Configuration

Create a file named `bridges.txt`:

```text
Bridge obfs4 YOUR_BRIDGE_HERE
Bridge obfs4 YOUR_SECOND_BRIDGE_HERE
```

Inject bridges:

```bash
python index.py --bridges bridges.txt
```

The toolkit will:

1. Backup your current Tor configuration
2. Add bridge settings
3. Restart Tor
4. Verify the connection

---

## Leak Protection

Start the built-in killswitch:

```bash
python index.py --killswitch
```

The toolkit continuously checks whether traffic is routed through Tor.

If Tor becomes unavailable or traffic is no longer routed through the Tor network, the network interface can be disabled automatically to prevent IP exposure.

---

## Example

Configure bridges and start monitoring:

```bash
python index.py --bridges bridges.txt --killswitch
```

---

## Logging

Logs are stored in:

```text
~/.privacy_toolkit/privacy_toolkit.log
```

---

## Disclaimer

This software is intended for privacy research, testing, and legitimate anonymity use cases. Users are responsible for complying with local laws and regulations. The authors assume no liability for misuse or damages resulting from the use of this software.
