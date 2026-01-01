export type ReviewSummary = {
  flights: number;
  hours: number;
  missingRegistration: number;
};

export type FlightRow = {
  id: string;
  date: string;
  registration: string;
  origin: string;
  destination: string;
  status: "OK" | "Needs review";
};

export type ImportResults = {
  imported: number;
  pending: number;
  failed: number;
  registrationMissing: number;
};

export type JobSnapshot = {
  reviewStatus: "idle" | "running" | "complete";
  importStatus: "idle" | "running" | "complete";
  reviewSummary?: ReviewSummary;
  flights?: FlightRow[];
  importResults?: ImportResults;
};

const mockFlights: FlightRow[] = [
  {
    id: "...inUjIKt47ulA",
    date: "2025-11-21",
    registration: "N12SB",
    origin: "KPAO",
    destination: "KTVL",
    status: "OK",
  },
  {
    id: "...DW98Fd25R6JM",
    date: "2025-11-23",
    registration: "—",
    origin: "KSJC",
    destination: "KSNS",
    status: "Needs review",
  },
  {
    id: "...c_U0DMhib1NA",
    date: "2025-11-24",
    registration: "N12SB",
    origin: "KPAO",
    destination: "KSOL",
    status: "OK",
  },
];

export async function fetchJobSnapshot(): Promise<JobSnapshot> {
  return {
    reviewStatus: "complete",
    importStatus: "complete",
    reviewSummary: {
      flights: 12,
      hours: 24.6,
      missingRegistration: 2,
    },
    flights: mockFlights,
    importResults: {
      imported: 46,
      pending: 0,
      failed: 0,
      registrationMissing: 2,
    },
  };
}

export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? "https://skybridge.localhost/api";
