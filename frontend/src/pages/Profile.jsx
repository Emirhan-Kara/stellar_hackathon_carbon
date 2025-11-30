import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkAuth } from '../utils/auth';
import ProjectCard from '../components/ProjectCard';
import './Profile.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function Profile() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [projectsLoading, setProjectsLoading] = useState(true);
  const [assets, setAssets] = useState([]);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [approving, setApproving] = useState(false);
  const [approvalStatus, setApprovalStatus] = useState(null);
  const [secretKey, setSecretKey] = useState('');
  const [showSecretKeyInput, setShowSecretKeyInput] = useState(false);

  useEffect(() => {
    const loadUser = async () => {
      const { authenticated, user: userData } = await checkAuth();
      if (!authenticated) {
        navigate('/connect');
        return;
      }
      setUser(userData);
      setLoading(false);
    };
    
    loadUser();
  }, [navigate]);

  useEffect(() => {
    const loadProjects = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/projects/my-projects`, {
          credentials: 'include',
        });
        if (response.ok) {
          const data = await response.json();
          setProjects(data);
        }
      } catch (error) {
        console.error('Error loading projects:', error);
      } finally {
        setProjectsLoading(false);
      }
    };

    if (user) {
      if (user.role === 'ISSUER') {
        loadProjects();
        loadAssets();
      }
    }
  }, [user]);

  const loadAssets = async () => {
    setAssetsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/issuer/assets`, {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        setAssets(data);
      }
    } catch (error) {
      console.error('Error loading assets:', error);
    } finally {
      setAssetsLoading(false);
    }
  };


  const handleApproveAdmin = async () => {
    if (!secretKey && showSecretKeyInput) {
      alert('Please enter your secret key');
      return;
    }

    setApproving(true);
    setApprovalStatus(null);

    try {
      const requestBody = showSecretKeyInput && secretKey 
        ? { secret_key: secretKey }
        : {};

      const response = await fetch(`${API_BASE_URL}/issuer/approve-admin-all`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(requestBody),
      });

      const data = await response.json();

      if (response.ok) {
        setApprovalStatus({
          type: 'success',
          message: data.message,
          approved_count: data.approved_count,
          total_count: data.total_count,
          failed_assets: data.failed_assets,
          approval_commands: data.approval_commands,
        });
        if (secretKey) {
          setSecretKey(''); // Clear secret key after use
        }
      } else {
        setApprovalStatus({
          type: 'error',
          message: data.detail || 'Failed to approve admin',
        });
      }
    } catch (error) {
      console.error('Error approving admin:', error);
      setApprovalStatus({
        type: 'error',
        message: error.message || 'Failed to approve admin',
      });
    } finally {
      setApproving(false);
    }
  };

  const handleLogout = async () => {
    try {
      // Call backend logout endpoint to clear cookie
      await fetch(`${API_BASE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      
      // Also clear cookie on client side as backup
      document.cookie = 'auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=;';
      
      // Dispatch custom event to notify header of logout
      window.dispatchEvent(new CustomEvent('auth-changed'));
      
      // Navigate to home
      navigate('/');
    } catch (error) {
      console.error('Logout error:', error);
      // Even if backend call fails, try to clear cookie and navigate
      document.cookie = 'auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=;';
      window.dispatchEvent(new CustomEvent('auth-changed'));
      navigate('/');
    }
  };

  if (loading) {
    return (
      <div className="profile-page">
        <div className="profile-container">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="profile-page">
      <div className="profile-container">
        <h1>Profile</h1>
        
        <div className="profile-card">
          <div className="profile-avatar">
            <i className="fa-solid fa-user"></i>
          </div>
          
          <div className="profile-info">
            <div className="info-item">
              <label>Username</label>
              <div className="info-value">{user.username || 'N/A'}</div>
            </div>
            
            <div className="info-item">
              <label>Email</label>
              <div className="info-value">{user.email || 'Not provided'}</div>
            </div>
            
            <div className="info-item">
              <label>Wallet Address</label>
              <div className="info-value wallet-address">
                {user.wallet_address}
              </div>
            </div>
          </div>
          
          <button className="logout-button" onClick={handleLogout}>
            <i className="fa-solid fa-sign-out-alt"></i>
            Logout
          </button>
        </div>

        {/* Pre-Approval Section for ISSUER */}
        {user.role === 'ISSUER' && (
          <div className="pre-approval-section">
            <h2>
              <i className="fa-solid fa-shield-halved"></i> Admin Pre-Approval
            </h2>
            <div className="pre-approval-card">
              <p className="pre-approval-description">
                Pre-approve the admin account to transfer tokens on your behalf. This allows the admin to act as a middleman during purchases without requiring your signature at the time of sale.
              </p>
              
              {assetsLoading ? (
                <p>Loading assets...</p>
              ) : assets.length === 0 ? (
                <p className="no-assets-message">
                  <i className="fa-solid fa-info-circle"></i> No assets found. Create a project and tokenize assets first.
                </p>
              ) : (
                <div className="assets-summary">
                  <p>
                    <strong>{assets.length}</strong> asset{assets.length !== 1 ? 's' : ''} found
                  </p>
                </div>
              )}

              <div className="approval-options">
                <label className="approval-option">
                  <input
                    type="checkbox"
                    checked={showSecretKeyInput}
                    onChange={(e) => setShowSecretKeyInput(e.target.checked)}
                  />
                  <span>Approve using secret key (development only - insecure)</span>
                </label>

                {showSecretKeyInput && (
                  <div className="secret-key-input">
                    <label>Secret Key:</label>
                    <input
                      type="password"
                      value={secretKey}
                      onChange={(e) => setSecretKey(e.target.value)}
                      placeholder="Enter your Stellar secret key"
                      className="secret-key-field"
                    />
                    <small className="warning-text">
                      ⚠️ Warning: Never share your secret key. This is for development only.
                    </small>
                  </div>
                )}
              </div>

              <button
                className="btn-approve"
                onClick={handleApproveAdmin}
                disabled={approving || assets.length === 0}
              >
                {approving ? (
                  <>
                    <i className="fa-solid fa-spinner fa-spin"></i> Approving...
                  </>
                ) : (
                  <>
                    <i className="fa-solid fa-check-circle"></i> Approve Admin for All Assets
                  </>
                )}
              </button>

              {approvalStatus && (
                <div className={`approval-status ${approvalStatus.type}`}>
                  {approvalStatus.type === 'success' ? (
                    <>
                      <i className="fa-solid fa-check-circle"></i>
                      <div>
                        <p><strong>{approvalStatus.message}</strong></p>
                        {approvalStatus.approved_count !== undefined && (
                          <p>Approved: {approvalStatus.approved_count} / {approvalStatus.total_count}</p>
                        )}
                        {approvalStatus.failed_assets && approvalStatus.failed_assets.length > 0 && (
                          <div className="failed-assets">
                            <p>Failed assets:</p>
                            <ul>
                              {approvalStatus.failed_assets.map((asset, idx) => (
                                <li key={idx}>{asset.asset_code}: {asset.error}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {approvalStatus.approval_commands && approvalStatus.approval_commands.length > 0 && (
                          <div className="approval-commands">
                            <p><strong>Manual approval commands:</strong></p>
                            <pre>
                              {approvalStatus.approval_commands.map((cmd, idx) => (
                                <div key={idx}>{cmd.command}</div>
                              ))}
                            </pre>
                          </div>
                        )}
                      </div>
                    </>
                  ) : (
                    <>
                      <i className="fa-solid fa-exclamation-circle"></i>
                      <p>{approvalStatus.message}</p>
                    </>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* My Projects Section - Only for ISSUER */}
        {user.role === 'ISSUER' && (
          <div className="projects-section">
            <h2>My Projects</h2>
            {projectsLoading ? (
              <p>Loading projects...</p>
            ) : projects.length === 0 ? (
              <div className="no-projects">
                <i className="fa-solid fa-folder-open"></i>
                <p>You haven't created any projects yet.</p>
                <button 
                  className="btn-primary" 
                  onClick={() => navigate('/issuer')}
                >
                  <i className="fa-solid fa-plus"></i> Create Your First Project
                </button>
              </div>
            ) : (
              <div className="projects-grid">
                {projects.map((project) => (
                  <ProjectCard key={project.id} project={project} />
                ))}
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

export default Profile;

