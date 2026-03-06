import { render, screen, waitFor } from "@testing-library/react";

import App from "@/App";

describe("runtime smoke", () => {
  test("app shell mounts without recursive update errors", async () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    try {
      render(<App />);

      await screen.findByText(/SKYBRIDGE/i);

      await waitFor(() => {
        const messages = errorSpy.mock.calls
          .flat()
          .map((value) => String(value))
          .join("\n");

        expect(messages).not.toMatch(/Maximum update depth exceeded/i);
        expect(messages).not.toMatch(/Minified React error #185/i);
      });
    } finally {
      errorSpy.mockRestore();
    }
  });
});
