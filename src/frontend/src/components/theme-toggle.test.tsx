import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";

import { ThemeToggle } from "@/components/theme-toggle";

type MockMediaQueryList = MediaQueryList & {
  setMatches: (matches: boolean) => void;
};

function mockMatchMedia(matches: boolean): MockMediaQueryList {
  let currentMatches = matches;
  const listeners = new Map<EventListenerOrEventListenerObject, EventListener>();
  const registerListener = (listener: EventListenerOrEventListenerObject) => {
    const callback =
      typeof listener === "function"
        ? (listener as EventListener)
        : ((event: Event) => listener.handleEvent(event));
    listeners.set(listener, callback);
  };
  const unregisterListener = (listener: EventListenerOrEventListenerObject) => {
    listeners.delete(listener);
  };
  const mediaQueryList = {
    get matches() {
      return currentMatches;
    },
    media: "(prefers-color-scheme: dark)",
    onchange: null,
    addListener: vi.fn((listener: (event: MediaQueryListEvent) => void) => {
      registerListener(listener as EventListener);
    }),
    removeListener: vi.fn((listener: (event: MediaQueryListEvent) => void) => {
      unregisterListener(listener as EventListener);
    }),
    addEventListener: vi.fn((_type: string, listener: EventListenerOrEventListenerObject) => {
      registerListener(listener);
    }),
    removeEventListener: vi.fn((_type: string, listener: EventListenerOrEventListenerObject) => {
      unregisterListener(listener);
    }),
    dispatchEvent: vi.fn(() => true),
    setMatches(nextMatches: boolean) {
      currentMatches = nextMatches;
      const event = {
        matches: nextMatches,
        media: this.media,
      } as MediaQueryListEvent;
      listeners.forEach((listener) => listener(event as unknown as Event));
    },
  } as MockMediaQueryList;
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation(() => mediaQueryList),
  });
  return mediaQueryList;
}

beforeEach(() => {
  mockMatchMedia(false);
});

afterEach(() => {
  window.localStorage.clear();
  document.documentElement.classList.remove("dark");
  vi.restoreAllMocks();
});

describe("ThemeToggle", () => {
  it("uses host system preference when no theme is stored", () => {
    mockMatchMedia(true);

    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("keeps saved light preference over host dark preference", () => {
    mockMatchMedia(true);
    window.localStorage.setItem("skybridge-theme", "light");

    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "false");
  });

  it("persists the chosen theme when toggled", () => {
    render(<ThemeToggle />);

    fireEvent.click(screen.getByRole("switch"));

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(window.localStorage.getItem("skybridge-theme")).toBe("dark");
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });

  it("tracks system preference changes when no theme is stored", () => {
    const mediaQuery = mockMatchMedia(false);

    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(false);

    act(() => {
      mediaQuery.setMatches(true);
    });

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });
});
