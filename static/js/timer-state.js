/**
 * ET-7: Timer State Management with Zustand-like functionality
 * Provides persistent timer state across page refreshes and navigation
 */

class TimerStateManager {
  constructor(candidateId, questionIndex) {
    this.candidateId = candidateId;
    this.questionIndex = questionIndex;
    this.storageKey = `timer_state_${candidateId}_${questionIndex}`;
    this.sessionKey = `session_start_${candidateId}_${questionIndex}`;
    
    this.state = {
      startTime: null,
      elapsedTime: 0,
      isPaused: false,
      isActive: false
    };
    
    this.listeners = new Set();
    this.autoSaveInterval = null;
    
    this.loadState();
  }
  
  // Load persisted state from sessionStorage
  loadState() {
    try {
      const savedState = sessionStorage.getItem(this.storageKey);
      const sessionStart = sessionStorage.getItem(this.sessionKey);
      
      if (savedState && sessionStart) {
        const parsedState = JSON.parse(savedState);
        const sessionStartTime = parseInt(sessionStart);
        const now = Date.now();
        
        // If session is still valid (less than 1 hour), restore state
        if (now - sessionStartTime < 3600000) {
          this.state = {
            ...parsedState,
            startTime: now - parsedState.elapsedTime,
            isActive: true
          };
          return true;
        }
      }
    } catch (error) {
      // Failed to load timer state - continue with fresh start
    }
    
    // Start fresh
    this.state.startTime = Date.now();
    this.state.isActive = true;
    sessionStorage.setItem(this.sessionKey, this.state.startTime.toString());
    return false;
  }
  
  // Save current state to sessionStorage
  saveState() {
    try {
      const stateToSave = {
        elapsedTime: this.getElapsedTime(),
        isPaused: this.state.isPaused,
        lastUpdated: Date.now()
      };
      
      sessionStorage.setItem(this.storageKey, JSON.stringify(stateToSave));
    } catch (error) {
      // Failed to save timer state - continue silently
    }
  }
  
  // Get current elapsed time in milliseconds
  getElapsedTime() {
    if (!this.state.isActive || !this.state.startTime) return 0;
    return Date.now() - this.state.startTime;
  }
  
  // Get formatted time string (MM:SS)
  getFormattedTime() {
    const elapsed = Math.floor(this.getElapsedTime() / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
  
  // Pause the timer
  pause() {
    if (this.state.isPaused) return;
    
    this.state.isPaused = true;
    this.state.elapsedTime = this.getElapsedTime();
    this.notifyListeners();
  }
  
  // Resume the timer
  resume() {
    if (!this.state.isPaused) return;
    
    this.state.startTime = Date.now() - this.state.elapsedTime;
    this.state.isPaused = false;
    this.notifyListeners();
  }
  
  // Stop the timer and clear state
  stop() {
    this.state.isActive = false;
    this.state.isPaused = true;
    
    // Clear session storage
    sessionStorage.removeItem(this.storageKey);
    sessionStorage.removeItem(this.sessionKey);
    
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval);
      this.autoSaveInterval = null;
    }
    
    this.notifyListeners();
  }
  
  // Subscribe to state changes
  subscribe(listener) {
    this.listeners.add(listener);
    
    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
    };
  }
  
  // Notify all listeners of state changes
  notifyListeners() {
    this.listeners.forEach(listener => {
      try {
        listener(this.state);
      } catch (error) {
        // Timer state listener error - continue silently
      }
    });
  }
  
  // Start auto-save functionality
  startAutoSave(intervalMs = 10000) {
    if (this.autoSaveInterval) {
      clearInterval(this.autoSaveInterval);
    }
    
    this.autoSaveInterval = setInterval(() => {
      if (this.state.isActive && !this.state.isPaused) {
        this.saveState();
      }
    }, intervalMs);
  }
  
  // Handle visibility changes
  handleVisibilityChange() {
    if (document.hidden) {
      this.pause();
      this.saveState();
    } else {
      this.resume();
    }
  }
}

/**
 * ET-7: Global timer state management
 * Provides singleton access to timer state across the application
 */
class GlobalTimerManager {
  constructor() {
    this.activeTimers = new Map();
    this.setupGlobalListeners();
  }
  
  // Get or create timer for specific candidate/question
  getTimer(candidateId, questionIndex) {
    const key = `${candidateId}_${questionIndex}`;
    
    if (!this.activeTimers.has(key)) {
      const timer = new TimerStateManager(candidateId, questionIndex);
      timer.startAutoSave();
      this.activeTimers.set(key, timer);
    }
    
    return this.activeTimers.get(key);
  }
  
  // Clean up timer for specific candidate/question
  cleanupTimer(candidateId, questionIndex) {
    const key = `${candidateId}_${questionIndex}`;
    const timer = this.activeTimers.get(key);
    
    if (timer) {
      timer.stop();
      this.activeTimers.delete(key);
    }
  }
  
  // Setup global event listeners
  setupGlobalListeners() {
    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
      this.activeTimers.forEach(timer => {
        timer.handleVisibilityChange();
      });
    });
    
    // Handle page unload
    window.addEventListener('beforeunload', () => {
      this.activeTimers.forEach(timer => {
        timer.saveState();
      });
    });
  }
}

// ET-7: Global timer manager instance
window.timerManager = new GlobalTimerManager();

// ET-7: Utility functions for easy integration
window.TimerUtils = {
  // Initialize timer for a question
  initTimer(candidateId, questionIndex, onUpdate) {
    const timer = window.timerManager.getTimer(candidateId, questionIndex);
    
    if (onUpdate) {
      timer.subscribe(onUpdate);
    }
    
    return timer;
  },
  
  // Clean up timer when leaving a question
  cleanupTimer(candidateId, questionIndex) {
    window.timerManager.cleanupTimer(candidateId, questionIndex);
  },
  
  // Get formatted time for display
  getFormattedTime(candidateId, questionIndex) {
    const timer = window.timerManager.getTimer(candidateId, questionIndex);
    return timer.getFormattedTime();
  }
};

