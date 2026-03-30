'use client';

import { create } from 'zustand';

type AppStore = {
  jobId: string | null;
  overrides: Record<string, string>;
  dismissedFields: string[];

  setJobId: (jobId: string | null) => void;
  setOverride: (field: string, value: string) => void;

  dismissField: (field: string) => void;
  removeDismissedField: (field: string) => void;

  resetEdits: () => void;
};

export const useAppStore = create<AppStore>((set) => ({
  jobId: null,
  overrides: {},
  dismissedFields: [],

  setJobId: (jobId) => set({ jobId }),

  setOverride: (field, value) =>
    set((state) => ({
      overrides: {
        ...state.overrides,
        [field]: value,
      },
    })),

  dismissField: (field) =>
    set((state) => ({
      dismissedFields: state.dismissedFields.includes(field)
        ? state.dismissedFields
        : [...state.dismissedFields, field],
    })),

  removeDismissedField: (field) =>
    set((state) => ({
      dismissedFields: state.dismissedFields.filter(
        (item) => item !== field
      ),
    })),

  resetEdits: () => set({ overrides: {}, dismissedFields: [] }),
}));