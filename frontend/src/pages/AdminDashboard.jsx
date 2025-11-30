import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkAuth } from '../utils/auth';
import './AdminDashboard.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function AdminDashboard() {
  const [user, setUser] = useState(null);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [processingId, setProcessingId] = useState(null);
  const [showApproveModal, setShowApproveModal] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState(null);
  const [adminNote, setAdminNote] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const loadData = async () => {
      try {
        // Check authentication
        const authResult = await checkAuth();
        if (!authResult.authenticated) {
          navigate('/connect');
          return;
        }

        const userData = authResult.user;
        setUser(userData);

        // Check if user is admin
        if (userData.role !== 'ADMIN') {
          setError('Access denied. Admin role required.');
          return;
        }

        // Load pending requests
        await loadRequests();
      } catch (err) {
        console.error('Error loading data:', err);
        setError('Failed to load dashboard data');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [navigate]);

  const loadRequests = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/admin/tokenization-requests`, {
        credentials: 'include',
      });

      if (!response.ok) {
        if (response.status === 403) {
          setError('Access denied. Admin role required.');
          return;
        }
        throw new Error('Failed to load requests');
      }

      const data = await response.json();
      setRequests(data);
    } catch (err) {
      console.error('Error loading requests:', err);
      setError('Failed to load tokenization requests');
    }
  };

  const handleApprove = async () => {
    if (!selectedRequest) return;

    setProcessingId(selectedRequest.id);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/admin/tokenization-requests/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          request_id: selectedRequest.id,
          ...(adminNote && { admin_note: adminNote }),  // Only include if not empty
        }),
      });

      if (!response.ok) {
        let errorMessage = 'Failed to approve request';
        try {
          const errorData = await response.json();
          // Handle FastAPI validation errors
          if (errorData.detail) {
            if (Array.isArray(errorData.detail)) {
              // Validation errors come as an array
              errorMessage = errorData.detail.map(err => `${err.loc?.join('.')}: ${err.msg}`).join(', ');
            } else if (typeof errorData.detail === 'string') {
              errorMessage = errorData.detail;
            } else {
              errorMessage = JSON.stringify(errorData.detail);
            }
          }
        } catch (e) {
          // If we can't parse the error, use the status text
          errorMessage = response.statusText || 'Failed to approve request';
        }
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setError(null); // Clear any previous errors
      setSuccess(`Request approved! Contract deployed at: ${data.contract_address}`);
      
      // Reload requests
      await loadRequests();
      setShowApproveModal(false);
      setSelectedRequest(null);
      setAdminNote('');
      
      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error('Error approving request:', err);
      setError(err.message || 'Failed to approve request');
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async () => {
    if (!selectedRequest || !adminNote.trim()) {
      setError('Please provide a reason for rejection');
      return;
    }

    setProcessingId(selectedRequest.id);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/admin/tokenization-requests/reject`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          request_id: selectedRequest.id,
          admin_note: adminNote,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to reject request');
      }

      setError(null); // Clear any previous errors
      setSuccess('Request rejected successfully');
      
      // Reload requests
      await loadRequests();
      setShowRejectModal(false);
      setSelectedRequest(null);
      setAdminNote('');
      
      // Clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      console.error('Error rejecting request:', err);
      setError(err.message || 'Failed to reject request');
    } finally {
      setProcessingId(null);
    }
  };

  const openApproveModal = (request) => {
    setSelectedRequest(request);
    setAdminNote('');
    setError(null); // Clear errors when opening modal
    setSuccess(null); // Clear success messages
    setShowApproveModal(true);
  };

  const openRejectModal = (request) => {
    setSelectedRequest(request);
    setAdminNote('');
    setError(null); // Clear errors when opening modal
    setSuccess(null); // Clear success messages
    setShowRejectModal(true);
  };

  if (loading) {
    return (
      <div className="admin-dashboard-page">
        <div className="admin-dashboard-container">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  if (error && !user) {
    return (
      <div className="admin-dashboard-page">
        <div className="admin-dashboard-container">
          <div className="error-message">
            <i className="fa-solid fa-exclamation-circle"></i>
            {error}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-dashboard-page">
      <div className="admin-dashboard-container">
        <h1>Admin Dashboard</h1>
        <p className="page-subtitle">Manage pending tokenization requests</p>

        {success && (
          <div className="success-message">
            <i className="fa-solid fa-check-circle"></i>
            {success}
          </div>
        )}

        {error && (
          <div className="error-message">
            <i className="fa-solid fa-exclamation-circle"></i>
            {error}
          </div>
        )}

        {requests.length === 0 ? (
          <div className="no-requests">
            <i className="fa-solid fa-check-circle"></i>
            <p>No pending tokenization requests</p>
          </div>
        ) : (
          <div className="requests-list">
            {requests.map((request) => (
              <div key={request.id} className="request-card">
                <div className="request-header">
                  <h3>Request #{request.id}</h3>
                  <span className="request-status pending">PENDING</span>
                </div>
                
                <div className="request-details">
                  <div className="detail-row">
                    <span className="detail-label">Project:</span>
                    <span className="detail-value">{request.project_name} ({request.project_identifier})</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Vintage Year:</span>
                    <span className="detail-value">{request.vintage_year}</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Quantity:</span>
                    <span className="detail-value">{parseFloat(request.quantity).toLocaleString()} tons</span>
                  </div>
                  <div className="detail-row">
                    <span className="detail-label">Issuer:</span>
                    <span className="detail-value">{request.issuer_username || 'N/A'}</span>
                  </div>
                  {request.serial_number_start && (
                    <div className="detail-row">
                      <span className="detail-label">Serial Numbers:</span>
                      <span className="detail-value">
                        {request.serial_number_start}
                        {request.serial_number_end ? ` - ${request.serial_number_end}` : ''}
                      </span>
                    </div>
                  )}
                  {request.proof_document_url && (
                    <div className="detail-row">
                      <span className="detail-label">Proof Document:</span>
                      <a 
                        href={`${API_BASE_URL}${request.proof_document_url}`} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="document-link"
                      >
                        <i className="fa-solid fa-file-pdf"></i> View Document
                      </a>
                    </div>
                  )}
                </div>

                <div className="request-actions">
                  <button
                    className="btn-approve"
                    onClick={() => openApproveModal(request)}
                    disabled={processingId === request.id}
                  >
                    <i className="fa-solid fa-check"></i>
                    {processingId === request.id ? 'Processing...' : 'Approve'}
                  </button>
                  <button
                    className="btn-reject"
                    onClick={() => openRejectModal(request)}
                    disabled={processingId === request.id}
                  >
                    <i className="fa-solid fa-times"></i>
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Approve Modal */}
        {showApproveModal && selectedRequest && (
          <div className="modal-overlay" onClick={() => setShowApproveModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h2>Approve Tokenization Request</h2>
              <p>Are you sure you want to approve this request? This will deploy a smart contract on the Stellar network.</p>
              
              <div className="modal-details">
                <p><strong>Project:</strong> {selectedRequest.project_name}</p>
                <p><strong>Vintage Year:</strong> {selectedRequest.vintage_year}</p>
                <p><strong>Quantity:</strong> {parseFloat(selectedRequest.quantity).toLocaleString()} tons</p>
                <p><strong>Symbol:</strong> {selectedRequest.project_identifier}-{selectedRequest.vintage_year}</p>
              </div>

              <div className="form-group">
                <label htmlFor="approve-note">Admin Note (optional):</label>
                <textarea
                  id="approve-note"
                  value={adminNote}
                  onChange={(e) => setAdminNote(e.target.value)}
                  placeholder="Add any notes about this approval..."
                  rows="3"
                />
              </div>

              <div className="modal-actions">
                <button
                  className="btn-cancel"
                  onClick={() => {
                    setShowApproveModal(false);
                    setSelectedRequest(null);
                    setAdminNote('');
                  }}
                >
                  Cancel
                </button>
                <button
                  className="btn-confirm-approve"
                  onClick={handleApprove}
                  disabled={processingId === selectedRequest.id}
                >
                  {processingId === selectedRequest.id ? 'Processing...' : 'Confirm Approval'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Reject Modal */}
        {showRejectModal && selectedRequest && (
          <div className="modal-overlay" onClick={() => setShowRejectModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h2>Reject Tokenization Request</h2>
              <p>Please provide a reason for rejecting this request.</p>
              
              <div className="form-group">
                <label htmlFor="reject-note">Rejection Reason (required):</label>
                <textarea
                  id="reject-note"
                  value={adminNote}
                  onChange={(e) => setAdminNote(e.target.value)}
                  placeholder="Explain why this request is being rejected..."
                  rows="4"
                  required
                />
              </div>

              <div className="modal-actions">
                <button
                  className="btn-cancel"
                  onClick={() => {
                    setShowRejectModal(false);
                    setSelectedRequest(null);
                    setAdminNote('');
                  }}
                >
                  Cancel
                </button>
                <button
                  className="btn-confirm-reject"
                  onClick={handleReject}
                  disabled={processingId === selectedRequest.id || !adminNote.trim()}
                >
                  {processingId === selectedRequest.id ? 'Processing...' : 'Confirm Rejection'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AdminDashboard;

