import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkAuth } from '../utils/auth';
import MapPicker from '../components/MapPicker';
import './Issuer.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function Issuer() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // Form data
  const [categories, setCategories] = useState([]);
  const [registries, setRegistries] = useState([]);
  const [categoryId, setCategoryId] = useState('');
  const [registryId, setRegistryId] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [country, setCountry] = useState('');
  const [latitude, setLatitude] = useState(39.9334);
  const [longitude, setLongitude] = useState(32.8597);
  const [image, setImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      const { authenticated } = await checkAuth();
      if (!authenticated) {
        navigate('/connect');
        return;
      }

      try {
        // Load categories
        const categoriesRes = await fetch(`${API_BASE_URL}/projects/categories`);
        if (categoriesRes.ok) {
          const cats = await categoriesRes.json();
          setCategories(cats);
        }

        // Load registries
        const registriesRes = await fetch(`${API_BASE_URL}/projects/registries`);
        if (registriesRes.ok) {
          const regs = await registriesRes.json();
          setRegistries(regs);
        }
      } catch (err) {
        console.error('Error loading data:', err);
      }
    };

    loadData();
  }, [navigate]);

  const handleImageChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setError('Image file too large. Maximum size is 5MB.');
        return;
      }
      if (!file.type.match(/^image\/(jpeg|jpg|png|webp)$/)) {
        setError('Invalid image type. Only JPEG, PNG, and WebP are allowed.');
        return;
      }
      setImage(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result);
      };
      reader.readAsDataURL(file);
      setError(null);
    }
  };

  const handleLocationSelect = (lat, lng) => {
    setLatitude(lat);
    setLongitude(lng);
  };

  const handleNext = () => {
    if (step === 1) {
      if (!categoryId || !registryId) {
        setError('Please select both category and registry');
        return;
      }
    } else if (step === 2) {
      if (!name.trim() || !country.trim()) {
        setError('Please fill in all required fields');
        return;
      }
    } else if (step === 3) {
      if (!latitude || !longitude) {
        setError('Please select a location on the map');
        return;
      }
    } else if (step === 4) {
      if (!image) {
        setError('Please upload an image');
        return;
      }
    }
    setError(null);
    setStep(step + 1);
  };

  const handleBack = () => {
    setError(null);
    setStep(step - 1);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('category_id', categoryId);
      formData.append('registry_id', registryId);
      formData.append('name', name);
      formData.append('description', description);
      formData.append('country', country);
      formData.append('latitude', latitude);
      formData.append('longitude', longitude);
      formData.append('image', image);

      const response = await fetch(`${API_BASE_URL}/projects/create`, {
        method: 'POST',
        body: formData,
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to create project');
      }

      const data = await response.json();
      setSuccess(true);
      
      // Redirect to profile after 2 seconds
      setTimeout(() => {
        navigate('/profile');
      }, 2000);
    } catch (err) {
      setError(err.message || 'An error occurred while creating the project');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="issuer-page">
        <div className="issuer-container">
          <div className="success-message">
            <i className="fa-solid fa-check-circle"></i>
            <h2>Project Created Successfully!</h2>
            <p>You are now an issuer. Redirecting to your profile...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="issuer-page">
      <div className="issuer-container">
        <h1>Become an Issuer</h1>
        <p className="issuer-subtitle">Create your first project to become an issuer</p>

        <div className="issuer-form-container">
          {/* Progress indicator */}
          <div className="form-progress">
            {[1, 2, 3, 4].map((num) => (
              <div key={num} className={`progress-step ${step >= num ? 'active' : ''}`}>
                <div className="step-number">{num}</div>
                <div className="step-label">
                  {num === 1 && 'Category'}
                  {num === 2 && 'Details'}
                  {num === 3 && 'Location'}
                  {num === 4 && 'Image'}
                </div>
              </div>
            ))}
          </div>

          {error && (
            <div className="error-message">
              <i className="fa-solid fa-exclamation-circle"></i>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="issuer-form">
            {/* Step 1: Category and Registry */}
            {step === 1 && (
              <div className="form-step">
                <h2>Select Category and Registry</h2>
                <div className="form-group">
                  <label htmlFor="category">Category *</label>
                  <select
                    id="category"
                    value={categoryId}
                    onChange={(e) => setCategoryId(e.target.value)}
                    required
                  >
                    <option value="">Select a category</option>
                    {categories.map((cat) => (
                      <option key={cat.id} value={cat.id}>
                        {cat.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label htmlFor="registry">Registry *</label>
                  <select
                    id="registry"
                    value={registryId}
                    onChange={(e) => setRegistryId(e.target.value)}
                    required
                  >
                    <option value="">Select a registry</option>
                    {registries.map((reg) => (
                      <option key={reg.id} value={reg.id}>
                        {reg.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            {/* Step 2: Project Details */}
            {step === 2 && (
              <div className="form-step">
                <h2>Project Details</h2>
                <div className="form-group">
                  <label htmlFor="name">Project Name *</label>
                  <input
                    type="text"
                    id="name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Enter project name"
                    required
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="description">Description</label>
                  <textarea
                    id="description"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Enter project description"
                    rows="5"
                  />
                </div>

                <div className="form-group">
                  <label htmlFor="country">Country *</label>
                  <input
                    type="text"
                    id="country"
                    value={country}
                    onChange={(e) => setCountry(e.target.value)}
                    placeholder="Enter country name"
                    required
                  />
                </div>
              </div>
            )}

            {/* Step 3: Location */}
            {step === 3 && (
              <div className="form-step">
                <h2>Select Project Location</h2>
                <p className="step-description">Click on the map to select the exact location</p>
                <div className="form-group">
                  <MapPicker
                    onLocationSelect={handleLocationSelect}
                    initialLat={latitude}
                    initialLng={longitude}
                  />
                </div>
                <div className="location-info">
                  <p>Selected: {latitude.toFixed(6)}, {longitude.toFixed(6)}</p>
                </div>
              </div>
            )}

            {/* Step 4: Image Upload */}
            {step === 4 && (
              <div className="form-step">
                <h2>Upload Project Image</h2>
                <div className="form-group">
                  <label htmlFor="image">Project Image *</label>
                  <div className="image-upload-area">
                    <input
                      type="file"
                      id="image"
                      accept="image/jpeg,image/jpg,image/png,image/webp"
                      onChange={handleImageChange}
                      required
                    />
                    {imagePreview && (
                      <div className="image-preview">
                        <img src={imagePreview} alt="Preview" />
                      </div>
                    )}
                  </div>
                  <p className="form-hint">Maximum file size: 5MB. Supported formats: JPEG, PNG, WebP</p>
                </div>
              </div>
            )}

            {/* Navigation buttons */}
            <div className="form-navigation">
              {step > 1 && (
                <button type="button" onClick={handleBack} className="btn-secondary">
                  <i className="fa-solid fa-arrow-left"></i> Back
                </button>
              )}
              {step < 4 ? (
                <button type="button" onClick={handleNext} className="btn-primary">
                  Next <i className="fa-solid fa-arrow-right"></i>
                </button>
              ) : (
                <button type="submit" disabled={loading} className="btn-primary">
                  {loading ? (
                    <>
                      <i className="fa-solid fa-spinner fa-spin"></i> Creating...
                    </>
                  ) : (
                    <>
                      <i className="fa-solid fa-check"></i> Create Project
                    </>
                  )}
                </button>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

export default Issuer;
