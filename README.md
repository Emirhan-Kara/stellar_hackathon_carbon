# Carbon Credit Tokenization Platform

A blockchain-based marketplace that tokenizes carbon credits as Real World Assets (RWA) on the Stellar network. This platform connects verified energy producers with global investors, making carbon credit trading transparent, secure, and accessible.

## What It Does

Think of this as a carbon credit stock market, but on the blockchain. Energy producers (like solar farms or wind projects) can register their carbon reduction projects, get them verified, and issue tokens representing their carbon credits. Investors can then buy these tokens directly using XLM (Stellar's native currency) through atomic swaps.

## How It Works

The platform operates with three main roles:

- **Issuers** (Energy Producers): Register projects, submit verification documents, and get their carbon credits tokenized. Once approved, their credits become tradeable tokens on the blockchain.

- **Users** (Buyers/Investors): Browse the marketplace, view available carbon credit projects, and purchase tokens using XLM. The platform handles the entire transaction flow securely.

- **Admin**: Acts as the trusted middleman, verifying projects, managing tokenization, and facilitating atomic swaps between buyers and sellers.

## Key Features

**Atomic Swaps**: When you buy carbon credits, the transaction happens on both sides (you get tokens, seller gets XLM) or nothing happens. No risk of partial transactions.

**Pre-Approval System**: Sellers can pre-approve the admin to manage their tokens, eliminating the need for manual signing during each transaction. This makes the marketplace more efficient.

**Project Verification**: All projects go through an approval process where admins verify documentation before tokenization. This ensures only legitimate carbon credits enter the marketplace.

## Technology Stack

- **Backend**: FastAPI (Python) with MySQL database
- **Frontend**: React.js with Vite
- **Blockchain**: Stellar network with Soroban smart contracts
- **Wallet Integration**: Freighter wallet for transaction signing
- **Smart Contracts**: Custom carbon controller contract for token management

## Important Points

The platform uses Stellar's Soroban smart contracts to create unique tokens for each carbon credit project. Each token represents a specific amount of carbon credits (measured in tons) from a verified project with a specific vintage year.

Transactions are handled through atomic swaps, ensuring both parties get what they expect or the transaction fails completely. The admin account facilitates these swaps and manages the tokenization process.

All carbon credit data, project information, and transaction records are stored in a MySQL database, while the actual tokens live on the Stellar blockchain. This hybrid approach gives us the flexibility of a database with the security and transparency of blockchain.

## Getting Started

1. Set up your `.env` file with database credentials, Stellar network settings, and admin keys
2. Install backend dependencies: `pip install -r backend/requirements.txt`
3. Install frontend dependencies: `npm install` in the `frontend` directory
4. Run the backend: `uvicorn backend.main:app --reload`
5. Run the frontend: `npm run dev` in the `frontend` directory

Make sure you have MySQL running and the database schema imported from `Dump20251130.sql`.
