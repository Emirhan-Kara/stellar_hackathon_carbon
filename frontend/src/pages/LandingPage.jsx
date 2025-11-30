import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { checkAuth } from '../utils/auth';
import Footer from '../components/Footer';
import './LandingPage.css';

function LandingPage() {
  const [activeTab, setActiveTab] = useState('INVESTOR');
  const [step, setStep] = useState(1);
  const [user, setUser] = useState(null);
  const navigate = useNavigate();
  const containerRef = useRef(null);

  // Smooth cursor tracking for sunlight
  const cursorX = useMotionValue(0);
  const cursorY = useMotionValue(0);
  const springConfig = { damping: 25, stiffness: 150 };
  const x = useSpring(cursorX, springConfig);
  const y = useSpring(cursorY, springConfig);

  useEffect(() => {
    const handleMouseMove = (e) => {
      cursorX.set(e.clientX);
      cursorY.set(e.clientY);
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [cursorX, cursorY]);

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((prev) => (prev >= 3 ? 1 : prev + 1));
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const loadUser = async () => {
      const { authenticated, user: userData } = await checkAuth();
      if (authenticated) {
        setUser(userData);
      }
    };
    loadUser();
  }, []);

  const handleMarketplace = () => {
    navigate('/marketplace');
  };

  const handleIssuer = () => {
    navigate('/issuer');
  };

  const investorSteps = [
    { id: 1, title: 'Connect Wallet', desc: 'Securely login using Freighter to access the Stellar Network.', icon: 'fa-wallet' },
    { id: 2, title: 'Select Green Asset', desc: 'Browse verified Solar and Wind projects with transparent data.', icon: 'fa-magnifying-glass' },
    { id: 3, title: 'Instant Swap', desc: 'Exchange USDC for Carbon Credits via atomic swaps on-chain.', icon: 'fa-rotate' }
  ];

  const issuerSteps = [
    { id: 1, title: 'Digitize Certification', desc: 'Upload verified PDFs. Gemini AI extracts key impact data.', icon: 'fa-file-pdf' },
    { id: 2, title: 'Mint Tokens', desc: 'Smart Contracts generate unique tokens representing 1 ton CO2 each.', icon: 'fa-coins' },
    { id: 3, title: 'Receive Liquidity', desc: 'Sell tokens instantly on the global decentralized exchange.', icon: 'fa-hand-holding-dollar' }
  ];

  const currentSteps = activeTab === 'INVESTOR' ? investorSteps : issuerSteps;

  return (
    <div className="landing-page" ref={containerRef}>
      {/* Cursor Sunlight Effect */}
      <motion.div
        className="sunlight-effect"
        style={{
          left: x,
          top: y,
        }}
      />

      {/* Hero Section */}
      <div className="hero-section">
        {/* Hero Content */}
        <div className="hero-content">

          <motion.h1
            className="hero-title"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
          >
            Carbon Trading <br />
            <span className="gradient-text">Reimagined.</span>
          </motion.h1>

          <motion.p
            className="hero-description"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            The world's first Real World Asset (RWA) marketplace bridging{' '}
            <span className="highlight">Verified Energy</span> producers with{' '}
            <span className="highlight">Global Capital</span> on the {' '}
            <span className="highlight">Stellar Blockchain.</span>
          </motion.p>

          <motion.div
            className="hero-buttons"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <motion.button
              className="btn-primary"
              onClick={handleMarketplace}
              whileHover={{ scale: 1.05, y: -2 }}
              whileTap={{ scale: 0.95 }}
            >
              <span>
                Check Out Marketplace
                {'  '}
                <i className="fa-solid fa-arrow-right"></i>
              </span>
            </motion.button>
            <motion.button
              className="btn-secondary"
              onClick={handleIssuer}
              whileHover={{ scale: 1.05, y: -2 }}
              whileTap={{ scale: 0.95 }}
            >
              <span>
                {user?.role === 'ISSUER' ? 'Add Project  ' : 'Become Issuer  '}
                <i className={user?.role === 'ISSUER' ? 'fa-solid fa-plus' : 'fa-solid fa-rocket'}></i>
              </span>
            </motion.button>
          </motion.div>
        </div>
      </div>

      {/* Stats Ticker */}
      <div className="stats-section">
        <div className="stats-container">
          <div className="stat-item">
            <div className="stat-label">Total Tokenized</div>
            <div className="stat-value">
              <i className="fa-solid fa-leaf"></i> 1,204,500 t
            </div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Market Cap</div>
            <div className="stat-value">$12.4M</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Active Projects</div>
            <div className="stat-value">42</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Avg. Settlement</div>
            <div className="stat-value highlight-green">~4.2s</div>
          </div>
        </div>
      </div>

      {/* Workflow Section */}
      <div className="workflow-section">
        <div className="workflow-container">
          <div className="workflow-header">
            <h2>How It Works</h2>
            <div className="tab-switcher">
              <button
                className={`tab-btn ${activeTab === 'INVESTOR' ? 'active' : ''}`}
                onClick={() => setActiveTab('INVESTOR')}
              >
                Investor View
              </button>
              <button
                className={`tab-btn ${activeTab === 'ISSUER' ? 'active' : ''}`}
                onClick={() => setActiveTab('ISSUER')}
              >
                Issuer View
              </button>
            </div>
          </div>

          <div className="workflow-content">
            {/* Left: Text Steps */}
            <div className="workflow-steps">
              {currentSteps.map((item) => (
                <motion.div
                  key={item.id}
                  className={`workflow-step ${step === item.id ? 'active' : ''}`}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ 
                    opacity: step === item.id ? 1 : 0.6,
                    x: 0,
                    scale: step === item.id ? 1.02 : 1
                  }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                >
                  <div className={`step-icon ${step === item.id ? 'active' : ''}`}>
                    <i className={`fa-solid ${item.icon}`}></i>
                  </div>
                  <div className="step-content">
                    <h3>{item.title}</h3>
                    <p>{item.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>

            {/* Right: Animated Diagram */}
            <div className="workflow-diagram">
              <svg className="diagram-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                <line
                  x1="10"
                  y1="50"
                  x2="50"
                  y2="50"
                  className="diagram-line"
                  strokeWidth="0.5"
                />
                <motion.line
                  x1="10"
                  y1="50"
                  x2="50"
                  y2="50"
                  className="diagram-line-active"
                  strokeWidth="0.5"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: step >= 2 ? 1 : 0 }}
                  transition={{ duration: 1 }}
                />
                <line
                  x1="50"
                  y1="50"
                  x2="90"
                  y2="50"
                  className="diagram-line"
                  strokeWidth="0.5"
                />
                <motion.line
                  x1="50"
                  y1="50"
                  x2="90"
                  y2="50"
                  className="diagram-line-active"
                  strokeWidth="0.5"
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: step >= 3 ? 1 : 0 }}
                  transition={{ duration: 1, delay: 0.5 }}
                />
              </svg>

              {/* Node 1 - Start */}
              <motion.div
                className={`diagram-node node-start ${step === 1 ? 'active' : ''}`}
                animate={{
                  scale: step === 1 ? 1.1 : 1,
                }}
                style={{
                  position: 'absolute',
                  left: '10%',
                  top: '50%',
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <i className={`fa-solid ${activeTab === 'INVESTOR' ? 'fa-user' : 'fa-industry'}`}></i>
                <span>{activeTab === 'INVESTOR' ? 'User' : 'Issuer'}</span>
              </motion.div>

              {/* Moving Particle */}
              <motion.div
                className="diagram-particle"
                animate={{
                  left: step === 1 ? '10%' : step === 2 ? '50%' : '90%',
                  opacity: step === 3 ? 0 : 1,
                }}
                transition={{ duration: 2, ease: "easeInOut" }}
                style={{
                  position: 'absolute',
                  top: '50%',
                  transform: 'translate(-50%, -50%)',
                }}
              />

              {/* Node 2 - Center */}
              <motion.div
                className={`diagram-node node-center ${step === 2 ? 'active' : ''}`}
                animate={{
                  scale: step === 2 ? 1.25 : 1,
                }}
                style={{
                  position: 'absolute',
                  left: '50%',
                  top: '50%',
                  transform: 'translate(-50%, -50%)',
                }}
              >
                <i className="fa-solid fa-cube"></i>
              </motion.div>

              {/* Node 3 - End */}
              <motion.div
                className={`diagram-node node-end ${step === 3 ? 'active' : ''}`}
                animate={{
                  scale: step === 3 ? 1.1 : 1,
                }}
                style={{
                  position: 'absolute',
                  right: '10%',
                  top: '50%',
                  transform: 'translate(50%, -50%)',
                }}
              >
                <i className={`fa-solid ${activeTab === 'INVESTOR' ? 'fa-coins' : 'fa-globe'}`}></i>
                <span>{activeTab === 'INVESTOR' ? 'Asset' : 'Market'}</span>
              </motion.div>
            </div>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}

export default LandingPage;

