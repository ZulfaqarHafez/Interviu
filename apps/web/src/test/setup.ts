import "@testing-library/jest-dom/vitest";

// recharts' ResponsiveContainer relies on ResizeObserver, which jsdom lacks.
// Provide a no-op global stub so chart-bearing components render in tests.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
