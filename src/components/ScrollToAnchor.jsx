import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';

// Custom hook for smooth scrolling to anchor links
function ScrollToAnchor() {
  const location = useLocation();
  const lastHashRef = useRef('');

  useEffect(() => {
    // Check if the URL has a hash
    if (location.hash) {
      // Store the hash to avoid unnecessary re-scrolling
      lastHashRef.current = location.hash;
      
      // Remove the '#' character
      const targetId = location.hash.substring(1);
      
      // Find the target element by ID
      const targetElement = document.getElementById(targetId);
      
      if (targetElement) {
        // Delay slightly to ensure DOM is ready
        setTimeout(() => {
          // Smooth scroll to the element
          targetElement.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          });
        }, 100);
      }
    }
  }, [location]);

  return null; // This component doesn't render anything
}

export default ScrollToAnchor;
