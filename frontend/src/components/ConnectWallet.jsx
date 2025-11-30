import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  isConnected, 
  requestAccess, 
  signMessage 
} from '@stellar/freighter-api';
import './ConnectWallet.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function ConnectWallet() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [walletAddress, setWalletAddress] = useState(null);
  const [needsRegistration, setNeedsRegistration] = useState(false);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [usernameAvailable, setUsernameAvailable] = useState(null);
  const [emailAvailable, setEmailAvailable] = useState(null);
  const [checkingAvailability, setCheckingAvailability] = useState(false);
  const [registrationLoading, setRegistrationLoading] = useState(false);

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      // Step 1: Check if Freighter is connected
      const connected = await isConnected();
      if (!connected.isConnected) {
        throw new Error('Freighter wallet is not installed or not connected. Please install Freighter extension.');
      }

      // Step 2: Request access and get public key
      const accessResult = await requestAccess();
      if (accessResult.error) {
        throw new Error(accessResult.error);
      }

      const publicKey = accessResult.address;
      setWalletAddress(publicKey);

      // Step 3: Request nonce from backend
      const nonceResponse = await fetch(`${API_BASE_URL}/auth/nonce`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ publicKey }),
        credentials: 'include', // Important for cookies
      });

      if (!nonceResponse.ok) {
        const errorData = await nonceResponse.json();
        throw new Error(errorData.detail || 'Failed to get nonce');
      }

      const { nonce } = await nonceResponse.json();

      // Step 4: Sign the nonce with Freighter
      const signResult = await signMessage(nonce, { address: publicKey });
      
      if (signResult.error) {
        throw new Error(signResult.error);
      }

      if (!signResult.signedMessage) {
        throw new Error('Failed to sign message');
      }

      // Step 5: Verify signature with backend
      const verifyResponse = await fetch(`${API_BASE_URL}/auth/freighter/verify`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          publicKey,
          signature: signResult.signedMessage,
          nonce,
        }),
        credentials: 'include', // Important for cookies
      });

      if (!verifyResponse.ok) {
        const errorData = await verifyResponse.json();
        throw new Error(errorData.detail || 'Verification failed');
      }

      const verifyData = await verifyResponse.json();
      
      if (verifyData.registered) {
        // User is already registered - login successful
        setSuccess(true);
        console.log('Login successful:', verifyData);
        // Notify header of auth change
        window.dispatchEvent(new CustomEvent('auth-changed'));
        // Navigate to marketplace after a short delay
        setTimeout(() => {
          navigate('/marketplace');
        }, 1000);
      } else {
        // User needs to complete registration - signup flow
        setNeedsRegistration(true);
        setWalletAddress(publicKey);
      }
      
    } catch (err) {
      setError(err.message || 'An error occurred during authentication');
      console.error('Authentication error:', err);
    } finally {
      setLoading(false);
    }
  };

  const checkAvailability = async (field, value) => {
    if (!value || value.length < 3) {
      if (field === 'username') setUsernameAvailable(null);
      if (field === 'email') setEmailAvailable(null);
      return;
    }

    setCheckingAvailability(true);
    try {
      const body = field === 'username' ? { username: value } : { email: value };
      const response = await fetch(`${API_BASE_URL}/auth/check-availability`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        if (field === 'username') {
          setUsernameAvailable(data.username_available);
        } else {
          setEmailAvailable(data.email_available);
        }
      }
    } catch (err) {
      console.error('Error checking availability:', err);
    } finally {
      setCheckingAvailability(false);
    }
  };

  const handleUsernameChange = (e) => {
    const value = e.target.value;
    setUsername(value);
    checkAvailability('username', value);
  };

  const handleEmailChange = (e) => {
    const value = e.target.value;
    setEmail(value);
    if (value) {
      checkAvailability('email', value);
    } else {
      setEmailAvailable(null);
    }
  };

  const handleCompleteRegistration = async (e) => {
    e.preventDefault();
    setRegistrationLoading(true);
    setError(null);

    try {
      if (!username || username.length < 3) {
        throw new Error('Username must be at least 3 characters');
      }

      if (usernameAvailable === false) {
        throw new Error('Username is already taken');
      }

      if (email && emailAvailable === false) {
        throw new Error('Email is already taken');
      }

      const response = await fetch(`${API_BASE_URL}/auth/complete-registration`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          wallet_address: walletAddress,
          username: username,
          email: email || null,
        }),
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Registration failed');
      }

      const data = await response.json();
      setSuccess(true);
      setNeedsRegistration(false);
      console.log('Registration completed:', data);
      // Notify header of auth change
      window.dispatchEvent(new CustomEvent('auth-changed'));
      // After successful signup, navigate to marketplace
      setTimeout(() => {
        navigate('/marketplace');
      }, 1000);
    } catch (err) {
      setError(err.message || 'An error occurred during registration');
      console.error('Registration error:', err);
    } finally {
      setRegistrationLoading(false);
    }
  };

  return (
    <div className="connect-wallet-container">
      <div className="connect-wallet-card">
        <h2>Connect with Freighter</h2>
        <p className="description">
          Sign in using your Stellar wallet. Make sure you have the Freighter extension installed.
        </p>
        
        {error && (
          <div className="error-message">
            {error}
          </div>
        )}
        
        {success && (
          <div className="success-message">
            ✓ Successfully authenticated! Your wallet is connected.
            {walletAddress && (
              <div className="wallet-address">
                Wallet: {walletAddress.slice(0, 8)}...{walletAddress.slice(-8)}
              </div>
            )}
          </div>
        )}

        {needsRegistration ? (
          <form onSubmit={handleCompleteRegistration} className="registration-form">
            <h3>Complete Your Registration</h3>
            <p className="description">
              Please provide a username and optional email to complete your account setup.
            </p>

            <div className="form-group">
              <label htmlFor="username">Username *</label>
              <input
                type="text"
                id="username"
                value={username}
                onChange={handleUsernameChange}
                required
                minLength={3}
                placeholder="Choose a username"
                className={usernameAvailable === false ? 'input-error' : usernameAvailable === true ? 'input-success' : ''}
              />
              {username && (
                <div className={`availability-indicator ${usernameAvailable === false ? 'error' : usernameAvailable === true ? 'success' : 'checking'}`}>
                  {checkingAvailability ? 'Checking...' : usernameAvailable === false ? '✗ Username taken' : usernameAvailable === true ? '✓ Username available' : ''}
                </div>
              )}
            </div>

            <div className="form-group">
              <label htmlFor="email">Email (optional)</label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={handleEmailChange}
                placeholder="your@email.com"
                className={emailAvailable === false ? 'input-error' : emailAvailable === true ? 'input-success' : ''}
              />
              {email && (
                <div className={`availability-indicator ${emailAvailable === false ? 'error' : emailAvailable === true ? 'success' : 'checking'}`}>
                  {checkingAvailability ? 'Checking...' : emailAvailable === false ? '✗ Email taken' : emailAvailable === true ? '✓ Email available' : ''}
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={registrationLoading || usernameAvailable === false || (email && emailAvailable === false) || !username}
              className="connect-button"
            >
              {registrationLoading ? 'Registering...' : 'Complete Registration'}
            </button>
          </form>
        ) : (
          <>
            <button
              onClick={handleConnect}
              disabled={loading}
              className="connect-button"
            >
              {loading ? 'Connecting...' : walletAddress ? 'Reconnect Wallet' : 'Connect Wallet'}
            </button>

            {walletAddress && !loading && !success && (
              <div className="wallet-info">
                <p>Connected: {walletAddress}</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default ConnectWallet;

