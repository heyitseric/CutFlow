import { useCallback, useEffect, useRef, useState } from 'react';

interface AudioPlayerState {
  playing: boolean;
  currentTime: number;
  duration: number;
}

/**
 * Audio playback hook with range support.
 * Call `play(start, end)` to play a specific time range.
 */
export function useAudioPlayer(audioUrl: string | null) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const endTimeRef = useRef<number | null>(null);
  const rafRef = useRef<number>(0);
  const [state, setState] = useState<AudioPlayerState>({
    playing: false,
    currentTime: 0,
    duration: 0,
  });

  // create / swap audio element when url changes
  useEffect(() => {
    if (!audioUrl) return;
    const audio = new Audio(audioUrl);
    audioRef.current = audio;

    audio.addEventListener('loadedmetadata', () => {
      setState((s) => ({ ...s, duration: audio.duration }));
    });
    audio.addEventListener('ended', () => {
      setState((s) => ({ ...s, playing: false }));
    });

    return () => {
      audio.pause();
      audio.src = '';
      cancelAnimationFrame(rafRef.current);
    };
  }, [audioUrl]);

  // animation frame loop to track progress
  const tick = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;

    setState((s) => ({ ...s, currentTime: audio.currentTime }));

    if (endTimeRef.current !== null && audio.currentTime >= endTimeRef.current) {
      audio.pause();
      endTimeRef.current = null;
      setState((s) => ({ ...s, playing: false }));
      return;
    }

    if (!audio.paused) {
      rafRef.current = requestAnimationFrame(tick);
    }
  }, []);

  const play = useCallback(
    (start?: number, end?: number) => {
      const audio = audioRef.current;
      if (!audio) return;

      if (start !== undefined) {
        audio.currentTime = start;
      }
      endTimeRef.current = end ?? null;
      audio.play();
      setState((s) => ({ ...s, playing: true }));
      rafRef.current = requestAnimationFrame(tick);
    },
    [tick],
  );

  const pause = useCallback(() => {
    audioRef.current?.pause();
    endTimeRef.current = null;
    cancelAnimationFrame(rafRef.current);
    setState((s) => ({ ...s, playing: false }));
  }, []);

  const toggle = useCallback(
    (start?: number, end?: number) => {
      if (state.playing) {
        pause();
      } else {
        play(start, end);
      }
    },
    [state.playing, play, pause],
  );

  return { ...state, play, pause, toggle };
}
