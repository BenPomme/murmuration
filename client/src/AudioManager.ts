export class AudioManager {
  private audioContext: AudioContext | null = null;
  private sounds: Map<string, HTMLAudioElement> = new Map();
  private masterVolume = 0.5;
  private enabled = true;

  constructor() {
    // Initialize with some basic sounds using Web Audio API fallbacks
    this.initializeBasicSounds();
  }

  private initializeBasicSounds() {
    // Create simple procedural sounds for immediate functionality
    this.createBeepSound('button_click', 800, 0.1);
    this.createBeepSound('beacon_place', 600, 0.2);
    this.createBeepSound('success', 1000, 0.3);
    this.createBeepSound('error', 300, 0.3);
  }

  private createBeepSound(name: string, frequency: number, duration: number) {
    try {
      // Create a simple beep sound using Web Audio API
      if (!this.audioContext) {
        this.audioContext = new AudioContext();
      }
      
      // Store the sound parameters for later use
      const soundData = { frequency, duration };
      (this.sounds as any).set(name, soundData);
    } catch (error) {
      console.warn('Audio context not available:', error);
    }
  }

  public playSound(soundName: string, volume: number = 1.0) {
    if (!this.enabled) return;

    try {
      const soundData = (this.sounds as any).get(soundName);
      if (soundData && this.audioContext) {
        this.playBeep(soundData.frequency, soundData.duration, volume * this.masterVolume);
      }
    } catch (error) {
      console.warn('Failed to play sound:', soundName, error);
    }
  }

  private playBeep(frequency: number, duration: number, volume: number) {
    if (!this.audioContext) return;

    const oscillator = this.audioContext.createOscillator();
    const gainNode = this.audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(this.audioContext.destination);

    oscillator.frequency.value = frequency;
    oscillator.type = 'sine';

    gainNode.gain.setValueAtTime(0, this.audioContext.currentTime);
    gainNode.gain.linearRampToValueAtTime(volume, this.audioContext.currentTime + 0.01);
    gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + duration);

    oscillator.start(this.audioContext.currentTime);
    oscillator.stop(this.audioContext.currentTime + duration);
  }

  public setMasterVolume(volume: number) {
    this.masterVolume = Math.max(0, Math.min(1, volume));
  }

  public setEnabled(enabled: boolean) {
    this.enabled = enabled;
  }

  public isEnabled(): boolean {
    return this.enabled;
  }

  // Game-specific convenience methods
  public playButtonClick() {
    this.playSound('button_click', 0.3);
  }

  public playBeaconPlace() {
    this.playSound('beacon_place', 0.4);
  }

  public playSuccess() {
    this.playSound('success', 0.5);
  }

  public playError() {
    this.playSound('error', 0.6);
  }
}

// Singleton instance
export const audioManager = new AudioManager();