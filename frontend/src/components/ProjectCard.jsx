import { useNavigate } from 'react-router-dom';
import './ProjectCard.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

function ProjectCard({ project }) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/project/${project.id}`);
  };

  return (
    <div className="project-card" onClick={handleClick}>
      {project.image_url && (
        <div className="project-image">
          <img 
            src={`${API_BASE_URL}${project.image_url}`} 
            alt={project.name}
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
        </div>
      )}
      <div className="project-content">
        <div className="project-header">
          <h3>{project.name}</h3>
          <span className="project-identifier">{project.project_identifier}</span>
        </div>
        <div className="project-meta">
          {project.category_name && (
            <span className="project-category">
              <i className="fa-solid fa-tag"></i> {project.category_name}
            </span>
          )}
          {project.registry_name && (
            <span className="project-registry">
              <i className="fa-solid fa-building"></i> {project.registry_name}
            </span>
          )}
        </div>
        {project.country && (
          <div className="project-location">
            <i className="fa-solid fa-location-dot"></i> {project.country}
          </div>
        )}
        {project.min_price && (
          <div className="project-price">
            <i className="fa-solid fa-coins"></i>
            <span className="price-label">From</span>
            <span className="price-value">{parseFloat(project.min_price).toFixed(2)} XLM</span>
            {project.max_price && parseFloat(project.max_price) !== parseFloat(project.min_price) && (
              <span className="price-range"> - {parseFloat(project.max_price).toFixed(2)} XLM</span>
            )}
            {project.asset_count > 0 && (
              <span className="asset-count"> ({project.asset_count} {project.asset_count === 1 ? 'asset' : 'assets'})</span>
            )}
          </div>
        )}
        {project.description && (
          <p className="project-description">
            {project.description.length > 150 
              ? `${project.description.substring(0, 150)}...` 
              : project.description}
          </p>
        )}
      </div>
    </div>
  );
}

export default ProjectCard;

