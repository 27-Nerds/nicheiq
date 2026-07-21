export type GithubConnectionStatus = "ACTIVE" | "REVOKED";
export type GithubDispatchStatus = "PENDING" | "SUCCEEDED" | "FAILED" | "UNKNOWN";

export interface GithubConnection {
  id: string;
  provider: "GITHUB";
  accountLogin: string;
  accountType: string | null;
  repositorySelection: string | null;
  status: GithubConnectionStatus;
  lastVerifiedAt: string | null;
  createdAt: string;
}

export interface GithubConnectionsResponse {
  enabled: boolean;
  connections: GithubConnection[];
}

export interface GithubRepository {
  id: string;
  name: string;
  fullName: string;
  htmlUrl: string;
  private: boolean;
  hasIssues: boolean;
}

export interface GithubIssuePayload {
  version: 1;
  destination: {
    repositoryId: string;
    owner: string;
    name: string;
    fullName: string;
  };
  request: {
    title: string;
    body: string;
  };
}

export interface GithubIssuePreview {
  provider: "GITHUB";
  adapterVersion: 1;
  connectionId: string;
  payloadFingerprint: string;
  payload: GithubIssuePayload;
}

export interface GithubHandoffDispatch {
  id: string;
  handoffId: string;
  provider: "GITHUB";
  adapterVersion: number;
  destinationContainerId: string;
  destination: GithubIssuePayload["destination"];
  payload: GithubIssuePayload;
  payloadFingerprint: string;
  status: GithubDispatchStatus;
  retryable: boolean;
  attemptCount: number;
  connectionId: string;
  providerResourceId: string | null;
  providerResourceNodeId: string | null;
  providerResourceNumber: number | null;
  providerResourceUrl: string | null;
  errorClass: string | null;
  errorCode: string | null;
  providerRequestStartedAt: string;
  settledAt: string | null;
  reconciledAt: string | null;
  createdAt: string;
  updatedAt: string;
}

export type GithubReconciliation =
  | "matched"
  | "not_found"
  | "multiple_matches"
  | "not_required";
