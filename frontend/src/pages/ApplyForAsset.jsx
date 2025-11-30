import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkAuth } from '../utils/auth';
import './ApplyForAsset.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function ApplyForAsset() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [projects, setProjects] = useState([]);
  const [projectsLoading, setProjectsLoading] = useState(true);

  // Form data
  const [projectId, setProjectId] = useState('');
  const [vintageYear, setVintageYear] = useState(new Date().getFullYear());
  const [quantity, setQuantity] = useState('');
  const [pricePerTon, setPricePerTon] = useState('');
  const [serialNumberStart, setSerialNumberStart] = useState('');
  const [serialNumberEnd, setSerialNumberEnd] = useState('');
  const [document, setDocument] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      const { authenticated, user } = await checkAuth();
      if (!authenticated) {
        navigate('/connect');
        return;
      }

      if (user?.role !== 'ISSUER') {
        navigate('/');
        return;
      }

      // Load user's projects
      try {
        const response = await fetch(`${API_BASE_URL}/projects/my-projects`, {
          credentials: 'include',
        });
        if (response.ok) {
          const data = await response.json();
          setProjects(data);
        }
      } catch (err) {
        console.error('Error loading projects:', err);
      } finally {
        setProjectsLoading(false);
      }
    };

    loadData();
  }, [navigate]);

  const handleDocumentChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 10 * 1024 * 1024) {
        setError('Document file too large. Maximum size is 10MB.');
        return;
      }
      if (file.type !== 'application/pdf') {
        setError('Invalid file type. Only PDF files are allowed.');
        return;
      }
      setDocument(file);
      setError(null);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    // Validation
    if (!projectId) {
      setError('Please select a project');
      setLoading(false);
      return;
    }
    if (!vintageYear || vintageYear < 2000 || vintageYear > new Date().getFullYear()) {
      setError('Please enter a valid vintage year');
      setLoading(false);
      return;
    }
    if (!quantity || parseFloat(quantity) <= 0) {
      setError('Please enter a valid quantity');
      setLoading(false);
      return;
    }
    if (pricePerTon && parseFloat(pricePerTon) <= 0) {
      setError('Price per ton must be greater than 0');
      setLoading(false);
      return;
    }
    if (!document) {
      setError('Please upload a proof document');
      setLoading(false);
      return;
    }

    try {
      const formData = new FormData();
      formData.append('project_id', projectId);
      formData.append('vintage_year', vintageYear);
      formData.append('quantity', quantity);
      if (pricePerTon) {
        formData.append('price_per_ton', pricePerTon);
      }
      formData.append('serial_number_start', serialNumberStart);
      formData.append('serial_number_end', serialNumberEnd);
      formData.append('proof_document', document);

      const response = await fetch(`${API_BASE_URL}/tokenization/create`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create tokenization request');
      }

      const data = await response.json();
      setSuccess(true);
      
      // Reset form
      setProjectId('');
      setVintageYear(new Date().getFullYear());
      setQuantity('');
      setPricePerTon('');
      setSerialNumberStart('');
      setSerialNumberEnd('');
      setDocument(null);
      
      // Redirect to profile after 3 seconds
      setTimeout(() => {
        navigate('/profile');
      }, 3000);
    } catch (err) {
      setError(err.message || 'An error occurred while creating the tokenization request');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="apply-asset-page">
        <div className="apply-asset-container">
          <div className="success-message">
            <i className="fa-solid fa-check-circle"></i>
            <h2>Tokenization Request Submitted!</h2>
            <p>Your request has been submitted and is pending admin approval.</p>
            <p>Redirecting to your profile...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="apply-asset-page">
      <div className="apply-asset-container">
        <h1>Apply for Asset Tokenization</h1>
        <p className="page-subtitle">Submit a request to tokenize carbon credits from your project</p>

        <div className="apply-asset-form-container">
          {error && (
            <div className="error-message">
              <i className="fa-solid fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          {projectsLoading ? (
            <p>Loading your projects...</p>
          ) : projects.length === 0 ? (
            <div className="no-projects">
              <i className="fa-solid fa-folder-open"></i>
              <p>You need to create a project first before applying for asset tokenization.</p>
              <button 
                className="btn-primary" 
                onClick={() => navigate('/issuer')}
              >
                <i className="fa-solid fa-plus"></i> Create Project
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="apply-asset-form">
              <div className="form-group">
                <label htmlFor="project">Select Project *</label>
                <select
                  id="project"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  required
                >
                  <option value="">Select a project</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.project_identifier} - {project.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="vintageYear">Vintage Year *</label>
                  <input
                    type="number"
                    id="vintageYear"
                    value={vintageYear}
                    onChange={(e) => setVintageYear(parseInt(e.target.value))}
                    min="2000"
                    max={new Date().getFullYear()}
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="quantity">Quantity (tons CO2) *</label>
                  <input
                    type="number"
                    id="quantity"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    step="0.0000001"
                    min="0.0000001"
                    placeholder="e.g., 1000.5"
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="pricePerTon">Price per Ton (XLM)</label>
                  <input
                    type="number"
                    id="pricePerTon"
                    value={pricePerTon}
                    onChange={(e) => setPricePerTon(e.target.value)}
                    step="0.01"
                    min="0"
                    placeholder="e.g., 2.5"
                  />
                  <p className="form-hint">Optional: Set the price buyers will pay per ton</p>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label htmlFor="serialStart">Certificate Serial Number (Start)</label>
                  <input
                    type="text"
                    id="serialStart"
                    value={serialNumberStart}
                    onChange={(e) => setSerialNumberStart(e.target.value)}
                    placeholder="e.g., VER-2023-001"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="serialEnd">Certificate Serial Number (End)</label>
                  <input
                    type="text"
                    id="serialEnd"
                    value={serialNumberEnd}
                    onChange={(e) => setSerialNumberEnd(e.target.value)}
                    placeholder="e.g., VER-2023-100"
                  />
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="document">Proof Document (PDF) *</label>
                <div className="document-upload-area">
                  <input
                    type="file"
                    id="document"
                    accept="application/pdf"
                    onChange={handleDocumentChange}
                    required
                  />
                  {document && (
                    <div className="document-info">
                      <i className="fa-solid fa-file-pdf"></i>
                      <span>{document.name}</span>
                      <span className="file-size">({(document.size / 1024 / 1024).toFixed(2)} MB)</span>
                    </div>
                  )}
                </div>
                <p className="form-hint">Maximum file size: 10MB. Only PDF files are allowed.</p>
              </div>

              <div className="form-navigation">
                <button type="submit" disabled={loading} className="btn-primary">
                  {loading ? (
                    <>
                      <i className="fa-solid fa-spinner fa-spin"></i> Submitting...
                    </>
                  ) : (
                    <>
                      <i className="fa-solid fa-paper-plane"></i> Submit Request
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

export default ApplyForAsset;

