import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface BankAccount {
  id: string;
  iban: string;
  balance: string;
  blocked_funds: string;
  available_balance: string;
  currency: string;
  account_type: string;
  account_type_display: string;
  parent_account?: string | null;
  parent_account_iban?: string;
  owner_name?: string;
  created_at: string;
}

export interface JuniorUser {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  pesel: string;
  role: 'PARENT' | 'JUNIOR';
}

export interface ApprovalRequest {
  id: string;
  request_type: 'TRANSFER' | 'CARD_PAYMENT' | 'BLIK_PAYMENT';
  request_type_display: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  status_display: string;
  junior: number;
  junior_name: string;
  account: string;
  account_iban: string;
  transfer?: string | null;
  card_transaction?: string | null;
  amount: string;
  target: string;
  created_at: string;
  decided_at?: string | null;
}

export interface JuniorBlikTransaction {
  id: string;
  klik_transaction_id: string;
  amount: string;
  currency: string;
  merchant_name: string;
  status: string;
  reject_reason?: string;
  created_at: string;
  completed_at?: string | null;
}

export interface JuniorActivitySummary {
  total_expenses: string;
  total_income: string;
  pending_expenses: string;
  expense_count: number;
  income_count: number;
  pending_count: number;
  operations_count: number;
  blik_total: string;
  blik_count: number;
  blik_pending: string;
}

export interface JuniorOperation {
  id: string;
  kind: 'TRANSFER_OUT' | 'TRANSFER_IN' | 'CARD' | 'BLIK';
  direction: 'IN' | 'OUT';
  title: string;
  counterparty: string;
  amount: string;
  status: string;
  status_display: string;
  category_label: string;
  system_route: string;
  reject_reason?: string;
  reject_reason_display?: string;
  currency?: string;
  created_at: string;
  processed_at?: string | null;
}

export interface JuniorActivity {
  account: BankAccount;
  prepaid_card: PrepaidCard | null;
  summary: JuniorActivitySummary;
  operations: JuniorOperation[];
  blik_transactions: JuniorBlikTransaction[];
}

export interface PrepaidCard {
  id: string;
  account: string;
  account_iban: string;
  masked_number: string;
  status: string;
  status_display: string;
  daily_limit: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class JuniorService {
  private http = inject(HttpClient);

  createJunior(data: {
    first_name: string;
    last_name: string;
    email: string;
    pesel: string;
    phone_number?: string;
    password: string;
    password_confirm: string;
    parent_account_id: string;
  }): Observable<{ user: JuniorUser; account: BankAccount }> {
    return this.http.post<{ user: JuniorUser; account: BankAccount }>('/api/accounts/junior/', data);
  }

  listAccounts(): Observable<BankAccount[]> {
    return this.http.get<BankAccount[]>('/api/accounts/');
  }

  listJuniors(): Observable<BankAccount[]> {
    return this.http.get<BankAccount[]>('/api/accounts/juniors/');
  }

  getJuniorActivity(accountId: string): Observable<JuniorActivity> {
    return this.http.get<JuniorActivity>(`/api/accounts/juniors/${accountId}/activity/`);
  }

  listApprovals(): Observable<ApprovalRequest[]> {
    return this.http.get<ApprovalRequest[]>('/api/approvals/');
  }

  approve(id: string): Observable<ApprovalRequest> {
    return this.http.post<ApprovalRequest>(`/api/approvals/${id}/approve/`, {});
  }

  reject(id: string): Observable<ApprovalRequest> {
    return this.http.post<ApprovalRequest>(`/api/approvals/${id}/reject/`, {});
  }

  listCards(): Observable<PrepaidCard[]> {
    return this.http.get<PrepaidCard[]>('/api/cards/');
  }

  cardPayment(cardId: string, data: { merchant_name: string; amount: string; transaction_type: string }) {
    return this.http.post(`/api/cards/${cardId}/payments/`, data);
  }
}
