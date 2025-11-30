import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, useScroll, useMotionValueEvent } from 'framer-motion';
import { checkAuth } from '../utils/auth';
import './Header.css';

function Header() {
  const location = useLocation();
  const navigate = useNavigate();
  const [isVisible, setIsVisible] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [theme, setTheme] = useState(() => {
    // Get theme from localStorage or default to dark
    const savedTheme = localStorage.getItem('theme');
    return savedTheme || 'dark';
  });
  const { scrollY } = useScroll();

  useEffect(() => {
    // Apply theme to document
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  useEffect(() => {
    // Check authentication status
    const verifyAuth = async () => {
      const { authenticated, user } = await checkAuth();
      setIsAuthenticated(authenticated);
      setUser(user);
    };
    
    verifyAuth();
    
    // Listen for auth changes (login/logout)
    const handleAuthChange = () => {
      verifyAuth();
    };
    
    window.addEventListener('auth-changed', handleAuthChange);
    
    // Check auth on route changes
    const interval = setInterval(verifyAuth, 5000); // Check every 5 seconds
    return () => {
      clearInterval(interval);
      window.removeEventListener('auth-changed', handleAuthChange);
    };
  }, [location]);

  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = scrollY.getPrevious() ?? 0;
    if (latest > previous && latest > 100) {
      setIsVisible(false);
    } else {
      setIsVisible(true);
    }
  });

  const handleLogin = () => {
    navigate('/connect');
  };

  const toggleTheme = () => {
    setTheme(prevTheme => prevTheme === 'dark' ? 'light' : 'dark');
  };

  return (
    <motion.header 
      className="header"
      initial={{ y: -100 }}
      animate={{ 
        y: isVisible ? 0 : -100,
        opacity: isVisible ? 1 : 0
      }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
    >
      <div className="header-container">
        {(location.pathname === '/admin' || (location.pathname === '/profile' && user?.role === 'ADMIN')) ? (
          <div className="logo" style={{ cursor: 'default' }}>
            Carbon<span className="logo-accent">Stellar</span>
          </div>
        ) : (
          <Link to="/" className="logo">
            Carbon<span className="logo-accent">Stellar</span>
          </Link>
        )}

        <nav className="nav">
          {location.pathname !== '/admin' && !(location.pathname === '/profile' && user?.role === 'ADMIN') && (
            <>
              <Link 
                to="/" 
                className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
              >
                Home
              </Link>
              <Link 
                to="/marketplace" 
                className={`nav-link ${location.pathname === '/marketplace' ? 'active' : ''}`}
              >
                Marketplace
              </Link>
              <Link 
                to="/issuer" 
                className={`nav-link ${location.pathname === '/issuer' ? 'active' : ''}`}
              >
                {user?.role === 'ISSUER' ? 'Add Project' : 'Become Issuer'}
              </Link>
              {user?.role === 'ISSUER' && (
                <Link 
                  to="/apply-asset" 
                  className={`nav-link ${location.pathname === '/apply-asset' ? 'active' : ''}`}
                >
                  Apply for Asset
                </Link>
              )}
            </>
          )}
          {user?.role === 'ADMIN' && (
            <Link 
              to="/admin" 
              className={`nav-link ${location.pathname === '/admin' ? 'active' : ''}`}
            >
              Admin Dashboard
            </Link>
          )}
        </nav>

        <div className="header-actions">
          <motion.button
            className="theme-toggle"
            onClick={toggleTheme}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? (
              <i className="fa-solid fa-sun"></i>
            ) : (
              <i className="fa-solid fa-moon"></i>
            )}
          </motion.button>
          {isAuthenticated ? (
            <motion.button
              className="profile-button"
              onClick={() => navigate('/profile')}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <i className="fa-solid fa-user"></i>
              {user?.username || 'Profile'}
            </motion.button>
          ) : (
            <motion.button
              className="login-button"
              onClick={handleLogin}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              Login
            </motion.button>
          )}
        </div>
      </div>
    </motion.header>
  );
}

export default Header;

