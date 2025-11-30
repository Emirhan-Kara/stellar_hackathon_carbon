import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import { Icon } from 'leaflet';
import { signTransaction, getAddress } from '@stellar/freighter-api';
import { checkAuth } from '../utils/auth';
import './ProjectDetail.css';
import 'leaflet/dist/leaflet.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Fix for default marker icons in React-Leaflet
delete Icon.Default.prototype._getIconUrl;
Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

function ProjectDetail() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);
  const [isOwner, setIsOwner] = useState(false);
  const [purchasingAssetId, setPurchasingAssetId] = useState(null); // Only set when purchase is actually processing
  const [purchaseAmounts, setPurchaseAmounts] = useState({}); // Store amounts per asset ID: { assetId: "amount" }
  const [purchaseError, setPurchaseError] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      const { authenticated, user: userData } = await checkAuth();
      if (!authenticated) {
        navigate('/connect');
        return;
      }
      setUser(userData);

      try {
        const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
          credentials: 'include',
        });
        if (response.ok) {
          const data = await response.json();
          setProject(data);
          setAssets(data.assets || []);
          setIsOwner(userData.user_id === data.issuer_id);
        } else if (response.status === 404) {
          navigate('/marketplace');
        }
      } catch (error) {
        console.error('Error loading project:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [projectId, navigate]);

  const handlePurchase = async (asset) => {
    const amount = purchaseAmounts[asset.id] || '';
    
    console.log('[Purchase] ===== PURCHASE INITIATED =====');
    console.log('[Purchase] Asset:', asset);
    console.log('[Purchase] Purchase amount:', amount);
    console.log('[Purchase] User:', user);
    
    // Immediate validation with logging
    if (!amount || amount.trim() === '') {
      console.error('[Purchase] ERROR: No purchase amount provided');
      setPurchaseError('Please enter a valid amount');
      return;
    }
    
    const amountNum = parseFloat(amount);
    if (isNaN(amountNum) || amountNum <= 0) {
      console.error('[Purchase] ERROR: Invalid amount:', amount);
      setPurchaseError('Please enter a valid amount');
      return;
    }

    console.log('[Purchase] Amount validated:', amountNum);
    setPurchasingAssetId(asset.id); // Set processing state
    setPurchaseError(null);

    console.log('[Purchase] Step 1: Initiating atomic swap via backend...');

    try {
      // Step 0: Check active Freighter account before building transaction
      console.log('[Purchase] Step 0: Checking active Freighter account...');
      let freighterAddress;
      try {
        const addressResult = await getAddress();
        if (addressResult.error) {
          throw new Error(`Failed to get Freighter address: ${addressResult.error}`);
        }
        freighterAddress = addressResult.address;
        console.log('[Purchase] Active Freighter account:', freighterAddress);
        console.log('[Purchase] Logged in user account:', user.wallet_address);
        
        if (freighterAddress !== user.wallet_address) {
          const proceed = window.confirm(
            `⚠️ Account Mismatch Detected!\n\n` +
            `You are logged in as: ${user.wallet_address}\n` +
            `But Freighter is active with: ${freighterAddress}\n\n` +
            `The transaction will be built for your logged-in account (${user.wallet_address}), ` +
            `but Freighter will try to sign with ${freighterAddress}, which will fail.\n\n` +
            `Please switch to account ${user.wallet_address} in Freighter, or log out and log in with ${freighterAddress}.\n\n` +
            `Click OK to continue anyway (this will likely fail), or Cancel to fix the account mismatch.`
          );
          
          if (!proceed) {
            throw new Error(
              `Account mismatch. Please switch to account ${user.wallet_address} in Freighter, or log in with account ${freighterAddress}.`
            );
          }
          
          console.log('[Purchase] User chose to proceed despite account mismatch');
        } else {
          console.log('[Purchase] ✓ Freighter account matches logged-in account');
        }
      } catch (addressError) {
        console.error('[Purchase] Error getting Freighter address:', addressError);
        throw new Error(`Failed to connect to Freighter: ${addressError.message || addressError}`);
      }
      
      // Step 1: Initiate atomic swap
      console.log('[Purchase] Step 1: Initiating atomic swap...');
      const swapResponse = await fetch(`${API_BASE_URL}/assets/atomic-swap`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          asset_id: asset.id,
          amount_xlm: amountNum,
          buyer_address: user.wallet_address,
        }),
      });

      console.log('[Purchase] Swap response status:', swapResponse.status);

      if (!swapResponse.ok) {
        const errorData = await swapResponse.json().catch(() => ({ detail: 'Unknown error' }));
        console.error('[Purchase] Swap initiation failed:', errorData);
        throw new Error(errorData.detail || 'Atomic swap failed');
      }

      const swapData = await swapResponse.json();
      console.log('[Purchase] Swap data received:', swapData);

      // Step 2: Sign XLM payment transaction
      console.log('[Purchase] Step 2: Signing XLM payment with Freighter...');
      console.log('[Purchase] XDR to sign:', swapData.buyer_payment_xdr.substring(0, 100) + '...');
      
      let signResult;
      try {
        console.log('[Purchase] Calling Freighter signTransaction...');
        signResult = await signTransaction(swapData.buyer_payment_xdr, {
          networkPassphrase: 'Test SDF Network ; September 2015',
          address: user.wallet_address,
        });
        console.log('[Purchase] Freighter signTransaction response:', signResult);
      } catch (freighterError) {
        console.error('[Purchase] Freighter signing exception:', freighterError);
        throw new Error(`Freighter signing failed: ${freighterError.message || freighterError}`);
      }

      if (signResult.error) {
        console.error('[Purchase] Signing error:', signResult.error);
        throw new Error(signResult.error || 'Transaction signing failed');
      }

      if (!signResult.signedTxXdr) {
        console.error('[Purchase] No signed XDR returned. Full result:', signResult);
        throw new Error('No signed transaction returned from Freighter');
      }

      const signedXdr = signResult.signedTxXdr;
      console.log('[Purchase] Transaction signed successfully');
      console.log('[Purchase] Signer address:', signResult.signerAddress);
      console.log('[Purchase] Expected buyer address:', user.wallet_address);
      
      // Verify that the signer matches the buyer (transaction source account)
      if (signResult.signerAddress !== user.wallet_address) {
        console.error('[Purchase] CRITICAL: Signer address mismatch!');
        console.error('[Purchase] Expected (transaction source):', user.wallet_address);
        console.error('[Purchase] Got (Freighter signer):', signResult.signerAddress);
        throw new Error(
          `Transaction authentication failed: The transaction was built for account ${user.wallet_address}, ` +
          `but Freighter signed it with account ${signResult.signerAddress}. ` +
          `Please switch to account ${user.wallet_address} in Freighter and try again.`
        );
      }
      
      console.log('[Purchase] Signer address verified');
      console.log('[Purchase] Signed transaction XDR:', signedXdr.substring(0, 100) + '...');

      // Step 4: Submit signed transaction
      console.log('[Purchase] Step 3: Submitting XLM payment to network...');
      const submitResponse = await fetch('https://horizon-testnet.stellar.org/transactions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `tx=${encodeURIComponent(signedXdr)}`,
      });

      if (!submitResponse.ok) {
        const errorText = await submitResponse.text();
        console.error('[Purchase] Submission failed:', errorText);
        
        let errorMessage = 'Transaction submission failed';
        try {
          const errorJson = JSON.parse(errorText);
          if (errorJson.extras && errorJson.extras.result_codes) {
            const codes = errorJson.extras.result_codes;
            if (codes.transaction === 'tx_bad_auth') {
              errorMessage = 'Transaction authentication failed. The transaction was signed by a different account than expected. Please ensure you are signed into Freighter with the correct account.';
            } else if (codes.transaction) {
              errorMessage = `Transaction failed: ${codes.transaction}`;
            }
            
            // Check for operation errors
            if (codes.operations && codes.operations[0]) {
              const opError = codes.operations[0];
              if (opError.includes('op_underfunded') || opError.includes('insufficient')) {
                errorMessage = 'Insufficient XLM balance. Please add more XLM to your wallet.';
              }
            }
          }
          
          if (errorJson.detail) {
            errorMessage += ` Details: ${errorJson.detail}`;
          }
        } catch {
          // If parsing fails, use the raw error text
          if (errorText.includes('insufficient balance') || errorText.includes('Insufficient balance')) {
            errorMessage = 'Insufficient XLM balance. Please ensure your wallet has enough XLM to cover the purchase amount plus transaction fees.';
          } else {
            errorMessage = `Transaction submission failed: ${errorText}`;
          }
        }
        
        throw new Error(errorMessage);
      }

      const submitResult = await submitResponse.json();
      console.log('[Purchase] XLM payment submitted. Hash:', submitResult.hash);
      console.log('[Purchase] Full submission result:', submitResult);

      // Wait a moment for transaction to be processed
      console.log('[Purchase] Waiting 2 seconds for transaction to be processed...');
      await new Promise(resolve => setTimeout(resolve, 2000));

      // Step 5: Complete swap (transfer tokens and send XLM to seller)
      console.log('[Purchase] Step 4: Completing swap (transferring tokens)...');
      console.log('[Purchase] Calling complete-swap with:', {
        asset_id: asset.id,
        amount_xlm: amountNum,
        buyer_address: user.wallet_address,
      });
      
      const completeResponse = await fetch(`${API_BASE_URL}/assets/complete-swap`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          asset_id: asset.id,
          amount_xlm: amountNum,
          buyer_address: user.wallet_address,
        }),
      });

      console.log('[Purchase] Complete-swap response status:', completeResponse.status);
      
      if (!completeResponse.ok) {
        const errorText = await completeResponse.text().catch(() => 'Unknown error');
        console.error('[Purchase] Swap completion failed. Status:', completeResponse.status);
        console.error('[Purchase] Error response:', errorText);
        
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { detail: errorText };
        }
        
        throw new Error(errorData.detail || `Failed to complete swap (status: ${completeResponse.status})`);
      }

      const completeResult = await completeResponse.json();
      console.log('[Purchase] Swap completed successfully:', completeResult);

      // Success!
      alert(
        `✅ Purchase Successful!\n\n` +
        `XLM Payment Hash: ${submitResult.hash}\n` +
        `Swap Completion Hash: ${completeResult.transaction_hash || 'N/A'}\n` +
        `Amount Paid: ${amountNum} XLM\n` +
        `Tokens Received: ${completeResult.tokens_purchased?.toFixed(7) || swapData.swap_details.tokens_purchased.toFixed(7)} tons\n\n` +
        `Your tokens have been transferred to your wallet!`
      );

      // Clear the amount for this asset
      setPurchaseAmounts(prev => {
        const newAmounts = { ...prev };
        delete newAmounts[asset.id];
        return newAmounts;
      });
      setPurchasingAssetId(null);
    } catch (error) {
      console.error('[Purchase] Purchase error:', error);
      console.error('[Purchase] Error details:', {
        message: error.message,
        stack: error.stack,
        name: error.name,
      });
      setPurchaseError(error.message || 'Failed to complete purchase. Check console for details.');
      setPurchasingAssetId(null);
    }
  };

  if (loading) {
    return (
      <div className="project-detail-page">
        <div className="project-detail-container">
          <div className="loading-state">
            <i className="fa-solid fa-spinner fa-spin"></i>
            <p>Loading project...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="project-detail-page">
        <div className="project-detail-container">
          <div className="error-state">
            <i className="fa-solid fa-exclamation-triangle"></i>
            <p>Project not found</p>
            <button className="btn-primary" onClick={() => navigate('/marketplace')}>
              Back to Marketplace
            </button>
          </div>
        </div>
      </div>
    );
  }

  const hasLocation = project.latitude && project.longitude;

  return (
    <div className="project-detail-page">
      <div className="project-detail-container">
        <button className="back-button" onClick={() => navigate('/marketplace')}>
          <i className="fa-solid fa-arrow-left"></i> Back to Marketplace
        </button>

        {/* Hero Section */}
        <div className="project-hero">
          {project.image_url && (
            <div className="project-hero-image">
              <img 
                src={`${API_BASE_URL}${project.image_url}`} 
                alt={project.name}
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
              />
            </div>
          )}
          <div className="project-hero-content">
            <div className="project-header-info">
              <div className="project-title-section">
                <h1>{project.name}</h1>
                <span className="project-identifier-badge">{project.project_identifier}</span>
              </div>
              {isOwner && (
                <span className="owner-badge">
                  <i className="fa-solid fa-crown"></i> Your Project
                </span>
              )}
            </div>
            
            <div className="project-meta-grid">
              {project.category_name && (
                <div className="meta-card">
                  <i className="fa-solid fa-tag"></i>
                  <div>
                    <span className="meta-label">Category</span>
                    <span className="meta-value">{project.category_name}</span>
                  </div>
                </div>
              )}
              {project.registry_name && (
                <div className="meta-card">
                  <i className="fa-solid fa-building"></i>
                  <div>
                    <span className="meta-label">Registry</span>
                    <span className="meta-value">{project.registry_name}</span>
                  </div>
                </div>
              )}
              {project.country && (
                <div className="meta-card">
                  <i className="fa-solid fa-location-dot"></i>
                  <div>
                    <span className="meta-label">Location</span>
                    <span className="meta-value">{project.country}</span>
                  </div>
                </div>
              )}
              {project.issuer_username && (
                <div className="meta-card">
                  <i className="fa-solid fa-user"></i>
                  <div>
                    <span className="meta-label">Issuer</span>
                    <span className="meta-value">{project.issuer_username}</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Description Section */}
        {project.description && (
          <div className="project-section">
            <h2 className="section-title">
              <i className="fa-solid fa-file-lines"></i> About This Project
            </h2>
            <p className="project-description">{project.description}</p>
          </div>
        )}

        {/* Map Section */}
        {hasLocation && (
          <div className="project-section">
            <h2 className="section-title">
              <i className="fa-solid fa-map-location-dot"></i> Project Location
            </h2>
            <div className="map-container">
              <MapContainer
                center={[project.latitude, project.longitude]}
                zoom={10}
                scrollWheelZoom={false}
                style={{ height: '100%', width: '100%', borderRadius: '12px' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />
                <Marker position={[project.latitude, project.longitude]}>
                  <Popup>
                    <strong>{project.name}</strong><br />
                    {project.country}
                  </Popup>
                </Marker>
              </MapContainer>
            </div>
          </div>
        )}

        {/* Assets Section */}
        <div className="project-section">
          <div className="section-header">
            <h2 className="section-title">
              <i className="fa-solid fa-coins"></i> Available Assets
            </h2>
            <span className="assets-count">{assets.length} {assets.length === 1 ? 'asset' : 'assets'}</span>
          </div>
          
          {assets.length === 0 ? (
            <div className="empty-state">
              <i className="fa-solid fa-box-open"></i>
              <h3>No Assets Available</h3>
              <p>This project doesn't have any assets available yet.</p>
            </div>
          ) : (
            <div className="assets-grid">
              {assets.map((asset) => (
                <div key={asset.id} className="asset-card">
                  <div className="asset-card-header">
                    <div>
                      <h3 className="asset-code">{asset.asset_code}</h3>
                      <span className="vintage-badge">Vintage {asset.vintage_year}</span>
                    </div>
                    {asset.is_frozen && (
                      <span className="frozen-badge">
                        <i className="fa-solid fa-lock"></i> Frozen
                      </span>
                    )}
                  </div>
                  
                  <div className="asset-stats">
                    <div className="stat-item">
                      <span className="stat-label">Total Supply</span>
                      <span className="stat-value">{parseFloat(asset.total_supply).toLocaleString()} tons</span>
                    </div>
                    {asset.price_per_ton && (
                      <div className="stat-item">
                        <span className="stat-label">Price per ton</span>
                        <span className="stat-value price">{parseFloat(asset.price_per_ton).toFixed(2)} XLM</span>
                      </div>
                    )}
                    {asset.contract_id && (
                      <div className="stat-item contract">
                        <span className="stat-label">Contract ID</span>
                        <span className="stat-value contract-id" title={asset.contract_id}>
                          {asset.contract_id.slice(0, 12)}...{asset.contract_id.slice(-8)}
                        </span>
                      </div>
                    )}
                  </div>
                  
                  {!isOwner && !asset.is_frozen && (
                    <div className="asset-purchase-section">
                      <div className="purchase-form">
                        <div className="input-wrapper">
                          <input
                            type="number"
                            placeholder="Enter XLM amount"
                            value={purchaseAmounts[asset.id] || ''}
                            onChange={(e) => {
                              const value = e.target.value;
                              setPurchaseAmounts(prev => ({
                                ...prev,
                                [asset.id]: value
                              }));
                              // Clear error when user starts typing
                              if (purchaseError) {
                                setPurchaseError(null);
                              }
                            }}
                            onFocus={() => {
                              // Input focused - no action needed
                            }}
                            min="0.0000001"
                            step="0.0000001"
                            disabled={purchasingAssetId === asset.id}
                          />
                          <span className="input-suffix">XLM</span>
                        </div>
                        <button
                          className="btn-purchase"
                          onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            console.log('[Purchase] ===== PURCHASE BUTTON CLICKED =====');
                            console.log('[Purchase] Amount:', purchaseAmounts[asset.id]);
                            console.log('[Purchase] Asset:', asset);
                            handlePurchase(asset);
                          }}
                          disabled={
                            purchasingAssetId === asset.id || 
                            !purchaseAmounts[asset.id] || 
                            parseFloat(purchaseAmounts[asset.id] || '0') <= 0 || 
                            isNaN(parseFloat(purchaseAmounts[asset.id] || '0'))
                          }
                        >
                          {purchasingAssetId === asset.id ? (
                            <>
                              <i className="fa-solid fa-spinner fa-spin"></i> Processing...
                            </>
                          ) : (
                            <>
                              <i className="fa-solid fa-shopping-cart"></i> Purchase
                            </>
                          )}
                        </button>
                      </div>
                      {purchasingAssetId === asset.id && purchaseError && (
                        <div className="error-message">
                          <i className="fa-solid fa-exclamation-circle"></i> {purchaseError}
                        </div>
                      )}
                    </div>
                  )}
                  
                  {isOwner && (
                    <div className="asset-owner-badge">
                      <i className="fa-solid fa-crown"></i> Your Asset
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default ProjectDetail;
