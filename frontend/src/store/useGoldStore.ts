import { create } from 'zustand';
import type { GoldPricePoint, GoldRealtime } from '../types/gold';
import * as goldApi from '../api/gold';

interface GoldState {
  // XAU/USD
  xauRealtime: GoldRealtime | null;
  xauHistory: GoldPricePoint[];
  xauLoading: boolean;

  // Au99.99
  auRealtime: GoldRealtime | null;
  auHistory: GoldPricePoint[];
  auLoading: boolean;

  // Actions
  fetchXauRealtime: () => Promise<void>;
  fetchAuRealtime: () => Promise<void>;
  fetchXauHistory: (days?: number) => Promise<void>;
  fetchAuHistory: (days?: number) => Promise<void>;
  fetchAll: () => Promise<void>;
}

export const useGoldStore = create<GoldState>((set) => ({
  xauRealtime: null,
  xauHistory: [],
  xauLoading: false,
  auRealtime: null,
  auHistory: [],
  auLoading: false,

  fetchXauRealtime: async () => {
    try {
      const data = await goldApi.fetchRealtime('xau-usd');
      set({ xauRealtime: data });
    } catch (err) {
      console.error('Failed to fetch XAU/USD realtime:', err);
    }
  },

  fetchAuRealtime: async () => {
    try {
      const data = await goldApi.fetchRealtime('au9999');
      set({ auRealtime: data });
    } catch (err) {
      console.error('Failed to fetch Au99.99 realtime:', err);
    }
  },

  fetchXauHistory: async (days = 365) => {
    set({ xauLoading: true });
    try {
      const data = await goldApi.fetchHistory('xau-usd', { limit: days });
      set({ xauHistory: data.data });
    } catch (err) {
      console.error('Failed to fetch XAU/USD history:', err);
    } finally {
      set({ xauLoading: false });
    }
  },

  fetchAuHistory: async (days = 365) => {
    set({ auLoading: true });
    try {
      const data = await goldApi.fetchHistory('au9999', { limit: days });
      set({ auHistory: data.data });
    } catch (err) {
      console.error('Failed to fetch Au99.99 history:', err);
    } finally {
      set({ auLoading: false });
    }
  },

  fetchAll: async () => {
    await Promise.all([
      useGoldStore.getState().fetchXauRealtime(),
      useGoldStore.getState().fetchAuRealtime(),
      useGoldStore.getState().fetchXauHistory(),
      useGoldStore.getState().fetchAuHistory(),
    ]);
  },
}));
