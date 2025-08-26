export interface SceneData {
  gameConfig?: {
    width: number;
    height: number;
    worldWidth: number;
    worldHeight: number;
  };
  serverUrl?: string;
  level?: number;
}

export interface MenuSceneData extends SceneData {
  showCredits?: boolean;
}

export interface GameSceneData extends SceneData {
  level: number;
  serverUrl: string;
}

export interface LoadingProgress {
  progress: number;
  file: string;
  totalFiles: number;
  loadedFiles: number;
}