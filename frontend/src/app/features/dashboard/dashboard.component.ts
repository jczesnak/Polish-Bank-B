import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DecimalPipe, NgClass, NgIf, NgFor, DatePipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';

export interface Account {
  id: string;
  iban: string;
  balance: string;
  blocked_funds: string;
  available_balance: string;
  currency: string;
  account_type: string;
  account_type_display: string;
}

interface Transfer {
  id: string;
  recipient_iban: string;
  recipient_name: string;
  amount: string;
  title: string;
  system_route: string;
  system_route_display: string;
  status: string;
  created_at: string;
}

const PAYMENT_SYSTEMS = [
  { name: 'Elixir Express', desc: 'Natychmiastowy • 24/7', icon: '⚡' },
  { name: 'Sorbnet', desc: 'Duże kwoty • Bezpieczny', icon: '🛡️' },
  { name: 'BLIK', desc: 'Mobilny • Natychmiastowy', icon: '📲' },
];

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe, NgClass, NgIf, NgFor, DatePipe],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private fb = inject(FormBuilder);

  accounts = signal<Account[]>([]);
  transfers = signal<Transfer[]>([]);
  loadingAccounts = signal(true);
  loadingTransfers = signal(true);
  showTransferModal = signal(false);
  integrationModalName = signal('');
  selectedTransferType = signal<'internal' | 'standard' | 'express' | 'sorbnet'>('internal');
  transferLoading = signal(false);
  transferError = signal('');

  readonly paymentSystems = PAYMENT_SYSTEMS;

  readonly transferTypes = [
    { key: 'internal' as const, label: 'Wewnętrzny' },
    { key: 'standard' as const, label: 'Standardowy' },
    { key: 'express' as const, label: 'Express' },
    { key: 'sorbnet' as const, label: 'Sorbnet' },
  ];

  readonly selectedTypeInfo = computed(() => {
    const map = {
      internal: { name: 'Przelew wewnętrzny', desc: 'Natychmiastowy przelew między rachunkami Polish Bank', time: 'Natychmiast', fee: 'Bezpłatny', limit: 'Bez limitu' },
      standard: { name: 'Elixir Standardowy', desc: 'Przelew krajowy – rozliczenie następnego dnia roboczego', time: '1-2 dni robocze', fee: 'Bezpłatny', limit: '100 000 PLN' },
      express:  { name: 'Express Elixir', desc: 'Natychmiastowy przelew krajowy 24/7/365', time: 'Do 10 sekund', fee: 'Bezpłatny', limit: '100 000 PLN' },
      sorbnet:  { name: 'SORBNET3', desc: 'Przelew wysokokwotowy RTGS przez Narodowy Bank Polski', time: 'Natychmiast (RTGS)', fee: '1 PLN', limit: 'Bez limitu' },
    };
    return map[this.selectedTransferType()];
  });

  readonly totalBalance = computed(() =>
    this.accounts().reduce((sum, acc) => sum + parseFloat(acc.balance), 0),
  );

  transferForm = this.fb.group({
    sender_account: ['', Validators.required],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    recipient: ['', Validators.required],
    account_number: ['', Validators.required],
    title: ['', Validators.required],
  });

  ngOnInit() {
    this.loadAccounts();
    this.loadTransfers();
  }

  private loadAccounts() {
    this.loadingAccounts.set(true);
    this.http.get<Account[]>('/api/accounts/').subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        this.loadingAccounts.set(false);
        if (accounts.length > 0) {
          this.transferForm.patchValue({ sender_account: accounts[0].id });
        }
      },
      error: () => this.loadingAccounts.set(false),
    });
  }

  private loadTransfers() {
    this.loadingTransfers.set(true);
    this.http.get<Transfer[]>('/api/transfers/').subscribe({
      next: (transfers) => {
        this.transfers.set(transfers);
        this.loadingTransfers.set(false);
      },
      error: () => this.loadingTransfers.set(false),
    });
  }

  openTransferModal() {
    this.showTransferModal.set(true);
    this.transferError.set('');
    this.transferForm.patchValue({ amount: '', recipient: '', account_number: '', title: '' });
  }

  closeTransferModal() { this.showTransferModal.set(false); }

  showIntegrationInfo(name: string) { this.integrationModalName.set(name); }

  submitTransfer() {
    if (this.transferForm.invalid) return;
    this.transferLoading.set(true);
    this.transferError.set('');

    const isInternal = this.selectedTransferType() === 'internal';
    const systemMap = { internal: 'INTERNAL', standard: 'ELIXIR', express: 'EXPRESS_ELIXIR', sorbnet: 'SORBNET' };
    const v = this.transferForm.value;

    const payload = {
      sender_account: v['sender_account'],
      recipient_iban: (v['account_number'] as string).replace(/\s/g, ''),
      recipient_name: v['recipient'],
      amount: v['amount'],
      title: v['title'],
      system_route: systemMap[this.selectedTransferType()],
    };

    const endpointUrl = isInternal ? '/api/internal/' : '/api/transfers/';

    this.http.post<Transfer>(endpointUrl, payload).subscribe({
      next: () => {
        this.transferLoading.set(false);
        this.closeTransferModal();
        this.loadAccounts();
        this.loadTransfers();
      },
      error: (err) => {
        this.transferLoading.set(false);
        const data = err?.error;
        if (typeof data === 'object') {
          this.transferError.set(Object.values(data).flat().join(' '));
        } else {
          this.transferError.set('Błąd podczas wysyłania przelewu.');
        }
      },
    });
  }
}