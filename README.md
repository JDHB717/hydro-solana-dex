# Hydra Protocol

## Overview

Hydra Protocol, formally known as [HydraSwap](https://www.hydraswap.io) is a Solana-based decentralized exchange that is dedicated to providing users with a CEX-level trading experience. Empowered by its game-changing Hydra Market Maker (HMM) core, it is a high-performance AMM focused on maximizing the returns for liquidity providers.
Our vision is to attract more liquidity into decentralized exchanges and bring the trading experience of the average DeFi user to the same level as centralized exchanges.

## Note

* Hydra Protocol is in active development and all API are subject to change
* This is currently experimental and unaudited software. Use at your own risk.

## Programs / Contracts 

All programs can be found in `./programs` and all integration tests can be found in `./tests`

* hydra-farming
* hydra-multisig
* hydra-pools
* hydra-staking
* hydra-vesting

## Contributing

### Install dependencies 

#### Installing rust:

Direction can be found [here](https://www.rust-lang.org/tools/install)

``` 
$ rustc --version 
rustc 1.57.0 (f1edd0429 2021-11-29)
```

#### Installing solana cli tools:

Directions can be found [here](https://docs.solana.com/cli/install-solana-cli-tools)

``` 
$ solana --version
solana-cli 1.8.5 (src:76c5c94a; feat:52865992)
```

#### Installing NodeJs 

Direction can be found [here](https://nodejs.org/en/)

``` 
$ node --version
v17.1.0
```

#### Installing Anchor:

Directions can be found [here](https://project-serum.github.io/anchor/getting-started/installation.html).

You can also use our own fork by running `make install_anchor`
``` 
$ anchor --version
anchor-cli 0.18.2
```

### Build

`anchor build`

### Deploy 

`anchor deploy`

### Test 

`anchor test`
