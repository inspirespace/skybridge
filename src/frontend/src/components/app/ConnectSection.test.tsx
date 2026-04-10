import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { ConnectSection } from "@/components/app/ConnectSection";
import { Accordion } from "@/components/ui/accordion";

function renderConnectSection() {
  render(
    <Accordion type="single" collapsible value="connect">
      <ConnectSection
        allowed={true}
        connected={false}
        signedIn={true}
        connectLocked={false}
        canConnect={false}
        startDate={undefined}
        endDate={undefined}
        startDateInput=""
        endDateInput=""
        setStartDateInput={vi.fn()}
        setEndDateInput={vi.fn()}
        dateRangeError={null}
        maxFlights=""
        cloudahoyEmail=""
        cloudahoyPassword=""
        flystoEmail=""
        flystoPassword=""
        setCloudahoyEmail={vi.fn()}
        setCloudahoyPassword={vi.fn()}
        setFlystoEmail={vi.fn()}
        setFlystoPassword={vi.fn()}
        setMaxFlights={vi.fn()}
        onConnectReview={vi.fn()}
        actionLoading={false}
        connectError={null}
        onRefresh={vi.fn()}
      />
    </Accordion>
  );
}

describe("ConnectSection", () => {
  it("marks temporary password fields as non-login credentials", () => {
    renderConnectSection();

    const passwordFields = screen.getAllByLabelText("Password");
    expect(passwordFields).toHaveLength(2);
    expect(passwordFields[0]).toHaveAttribute("autocomplete", "new-password");
    expect(passwordFields[1]).toHaveAttribute("autocomplete", "new-password");
    expect(passwordFields[0]).not.toHaveAttribute("name");
    expect(passwordFields[1]).not.toHaveAttribute("name");
  });

  it("does not render hidden username/password decoy inputs", () => {
    renderConnectSection();

    expect(document.querySelector('input[name="username"]')).toBeNull();
    expect(document.querySelector('input[name="password"]')).toBeNull();
    expect(document.querySelector('input[autocomplete="current-password"]')).toBeNull();
  });
});
