/**
 * Testes unitários do hook useReducedMotion (W8-08).
 */

import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MEDIA_QUERY_MOVIMENTO_REDUZIDO, useReducedMotion } from './useReducedMotion';

describe('useReducedMotion (W8-08)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('retorna false quando matchMedia não indica preferência por movimento reduzido', () => {
    vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
  });

  it('retorna true quando matchMedia indica prefers-reduced-motion: reduce', () => {
    vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
      matches: query === MEDIA_QUERY_MOVIMENTO_REDUZIDO,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });

  it('atualiza quando a preferência de mídia muda', () => {
    let ouvinte: ((e: { matches: boolean }) => void) | null = null;

    vi.stubGlobal('matchMedia', vi.fn((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn((_, fn) => {
        ouvinte = fn;
      }),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })));

    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);

    // Simula a mudança no sistema operacional
    act(() => {
      ouvinte?.({ matches: true });
    });

    expect(result.current).toBe(true);
  });
});
