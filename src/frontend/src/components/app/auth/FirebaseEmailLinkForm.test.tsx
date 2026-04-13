import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FirebaseEmailLinkForm } from "./FirebaseEmailLinkForm";

describe("FirebaseEmailLinkForm", () => {
  it("submits the form when Enter is pressed in the email field", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();

    render(
      <FirebaseEmailLinkForm
        label="Passwordless email link"
        email=""
        onEmailChange={vi.fn()}
        onSend={onSend}
        buttonLabel="Send link"
      />
    );

    const input = screen.getByLabelText(/passwordless email link/i);
    await user.type(input, "pilot@example.com{enter}");

    expect(onSend).toHaveBeenCalledTimes(1);
  });

  it("uses native email autofill-friendly attributes", () => {
    render(
      <FirebaseEmailLinkForm
        label="Passwordless email link"
        email=""
        onEmailChange={vi.fn()}
        onSend={vi.fn()}
        buttonLabel="Send link"
      />
    );

    const input = screen.getByLabelText(/passwordless email link/i);

    expect(input).toHaveAttribute("type", "email");
    expect(input).toHaveAttribute("name", "email");
    expect(input).toHaveAttribute("autocomplete", "email");
    expect(input).toHaveAttribute("inputmode", "email");
  });

  it("disables the email field while a sign-in action is in flight", () => {
    render(
      <FirebaseEmailLinkForm
        label="Passwordless email link"
        email=""
        onEmailChange={vi.fn()}
        onSend={vi.fn()}
        buttonLabel="Send link"
        disabled
      />
    );

    expect(screen.getByLabelText(/passwordless email link/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /send link/i })).toBeDisabled();
  });
});
