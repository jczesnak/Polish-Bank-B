import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PhoneAlias {
  id: string;
  phone: string;
  account: string;
  account_iban: string;
  klik_alias_id: string | null;
  zone: string;
  created_at: string;
}

export interface P2PTransferResult {
  message: string;
  transfer_id: string;
  recipient_phone: string;
  recipient_name: string;
  recipient_iban: string;
  recipient_bank: string;
  amount: string;
  system_route: string;
  status: string;
  contact_saved: boolean;
}

export interface P2pContact {
  id: string;
  name: string;
  phone: string;
  created_at: string;
}

export interface LookupResult {
  found: boolean;
  phone: string;
  bank_id?: string;
  bank_code?: string;
  iban?: string;
}

@Injectable({ providedIn: 'root' })
export class P2pService {
  private http = inject(HttpClient);
  private base = '/api/blik/p2p';

  listAliases(): Observable<PhoneAlias[]> {
    return this.http.get<PhoneAlias[]>(`${this.base}/aliases/`);
  }

  registerAlias(data: { account_id: string; phone?: string }): Observable<PhoneAlias> {
    return this.http.post<PhoneAlias>(`${this.base}/aliases/`, data);
  }

  deleteAlias(phone: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/aliases/${encodeURIComponent(phone)}/`);
  }

  lookup(phone: string): Observable<LookupResult> {
    return this.http.get<LookupResult>(`${this.base}/lookup/${encodeURIComponent(phone)}/`);
  }

  transfer(data: {
    sender_account: string;
    recipient_phone: string;
    recipient_name?: string;
    save_contact?: boolean;
    amount: string;
    title: string;
  }): Observable<P2PTransferResult> {
    return this.http.post<P2PTransferResult>(`${this.base}/transfer/`, data);
  }

  listContacts(): Observable<P2pContact[]> {
    return this.http.get<P2pContact[]>(`${this.base}/contacts/`);
  }

  addContact(data: { name: string; phone: string }): Observable<P2pContact> {
    return this.http.post<P2pContact>(`${this.base}/contacts/`, data);
  }

  deleteContact(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/contacts/${id}/`);
  }
}
