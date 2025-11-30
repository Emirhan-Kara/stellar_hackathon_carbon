const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Check if user is authenticated by verifying JWT cookie
 */
export async function checkAuth() {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/me`, {
      method: 'GET',
      credentials: 'include',
    });
    
    if (response.ok) {
      const data = await response.json();
      return { authenticated: true, user: data };
    }
    return { authenticated: false, user: null };
  } catch (error) {
    console.error('Auth check error:', error);
    return { authenticated: false, user: null };
  }
}

/**
 * Simple check if auth cookie exists (client-side only)
 * This is a quick check, but not secure - server should verify
 */
export function hasAuthCookie() {
  return document.cookie.split(';').some(cookie => cookie.trim().startsWith('auth_token='));
}

