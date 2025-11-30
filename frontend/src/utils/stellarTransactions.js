/**
 * Stellar Transaction Utilities
 * Helper functions for building and executing Stellar transactions
 */

const HORIZON_TESTNET_URL = 'https://horizon-testnet.stellar.org';
const HORIZON_MAINNET_URL = 'https://horizon.stellar.org';
const NETWORK_PASSPHRASE_TESTNET = 'Test SDF Network ; September 2015';
const NETWORK_PASSPHRASE_MAINNET = 'Public Global Stellar Network ; September 2015';

/**
 * Get Horizon server URL based on network
 */
function getHorizonUrl(network = 'testnet') {
  return network === 'testnet' ? HORIZON_TESTNET_URL : HORIZON_MAINNET_URL;
}

/**
 * Get network passphrase
 */
function getNetworkPassphrase(network = 'testnet') {
  return network === 'testnet' 
    ? NETWORK_PASSPHRASE_TESTNET 
    : NETWORK_PASSPHRASE_MAINNET;
}

/**
 * Fetch account data from Horizon
 */
export async function fetchAccountData(publicKey, network = 'testnet') {
  const horizonUrl = getHorizonUrl(network);
  try {
    const response = await fetch(`${horizonUrl}/accounts/${publicKey}`);
    if (!response.ok) {
      throw new Error(`Failed to fetch account: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching account data:', error);
    throw error;
  }
}

/**
 * Build a payment transaction XDR
 * This creates a transaction that sends XLM from one account to another
 */
export async function buildPaymentTransactionXDR(
  fromPublicKey,
  toPublicKey,
  amountXLM,
  memo = null,
  network = 'testnet'
) {
  try {
    // Fetch source account data
    const account = await fetchAccountData(fromPublicKey, network);
    const sequenceNumber = account.sequence;
    
    // Convert XLM to stroops (1 XLM = 10,000,000 stroops)
    const amountStroops = Math.floor(parseFloat(amountXLM) * 10000000);
    
    // Build transaction envelope
    // Note: This is a simplified version. In production, you'd use Stellar SDK
    // For now, we'll use a backend endpoint to build the transaction
    const transactionData = {
      sourceAccount: fromPublicKey,
      destination: toPublicKey,
      amount: amountStroops,
      sequence: sequenceNumber,
      memo: memo,
      network: network,
      networkPassphrase: getNetworkPassphrase(network),
    };
    
    return transactionData;
  } catch (error) {
    console.error('Error building transaction:', error);
    throw error;
  }
}

/**
 * Create a simple payment transaction using Freighter
 * This is a helper that uses Freighter's transaction signing capabilities
 */
export async function createPaymentWithFreighter(
  fromPublicKey,
  toPublicKey,
  amountXLM,
  memo = null,
  network = 'testnet'
) {
  // Note: Freighter doesn't directly build transactions
  // We need to either:
  // 1. Use a backend service to build the transaction XDR
  // 2. Use Stellar SDK in the frontend (requires npm package)
  // 3. Use Freighter's transaction signing with a pre-built XDR
  
  // For now, return the payment details that can be used with a backend service
  return {
    from: fromPublicKey,
    to: toPublicKey,
    amount: amountXLM,
    memo: memo,
    network: network,
  };
}

