import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DecimalPipe, NgClass, NgIf, NgFor, DatePipe } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';

export interface Account { id: string; iban: string; balance: string; blocked_funds: string; available_balance: string; currency: string; account_type: string; account_type_display: string; }

export interface Transfer { 
  id: string; 
  recipient_iban: string; 
  recipient_name: string; 
  amount: string; 
  title: string; 
  system_route: string; 
  system_route_display: string; 
  status: string; 
  created_at: string;
  direction?: 'IN' | 'OUT';
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe, NgClass, NgIf, NgFor, DatePipe],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  public auth = inject(AuthService);
  private fb = inject(FormBuilder);

  user = this.auth.user; 
  accounts = signal<Account[]>([]);
  transfers = signal<Transfer[]>([]);
  loadingAccounts = signal(true);
  loadingTransfers = signal(true);
  
  // Przelew - stan
  selectedTransferType = signal<'internal' | 'standard' | 'express' | 'sorbnet'>('standard');
  transferLoading = signal(false);
  transferError = signal('');

  // BLIK - stan symulacji
  blikCode = signal<string | null>(null);
  blikTimeLeft = signal<number>(0);
  blikInterval: any;

  // Widget: Kategorie Wydatków (Mockup danych statycznych)
  spendingCategories = [
    { name: 'Zakupy i markety', icon: '🛒', amount: 3450, percentage: 75 },
    { name: 'Rachunki i opłaty', icon: '🏠', amount: 1800, percentage: 40 },
    { name: 'Transport', icon: '🚗', amount: 850, percentage: 20 },
    { name: 'Rozrywka', icon: '🍿', amount: 420, percentage: 10 },
  ];

  readonly transferTypes = [
    { key: 'internal' as const, label: 'Wewnętrzny' },
    { key: 'standard' as const, label: 'Elixir' },
    { key: 'express' as const, label: 'Express' },
    { key: 'sorbnet' as const, label: 'Sorbnet' },
  ];

  readonly selectedTypeInfo = computed(() => {
    const map = {
      internal: { time: 'Zaksięgujemy natychmiast', fee: 'Darmowy' },
      standard: { time: 'Rozliczenie w sesjach KIR', fee: 'Darmowy' },
      express:  { time: 'Przelew natychmiastowy', fee: 'Darmowy' },
      sorbnet:  { time: 'System RTGS dla dużych kwot', fee: 'Prowizja 1 PLN' },
    };
    return map[this.selectedTransferType()];
  });

  readonly totalBalance = computed(() =>
    this.accounts().reduce((sum, acc) => sum + parseFloat(acc.balance), 0),
  );

  transferForm = this.fb.group({
    sender_account: [''],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    recipient: [''], 
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
        // Ponieważ backend zwraca tylko nasze wychodzące przelewy, 
        // oznaczamy je jako 'OUT', aby zachować spójność z widokiem.
        const mappedTransfers = transfers.map(t => ({
          ...t,
          direction: 'OUT'
        })) as Transfer[];

        this.transfers.set(mappedTransfers);
        this.loadingTransfers.set(false);
      },
      error: () => this.loadingTransfers.set(false),
    });
  }

  generateBlik() {
    const code = Math.floor(100000 + Math.random() * 900000).toString();
    this.blikCode.set(code);
    this.blikTimeLeft.set(120);

    if (this.blikInterval) clearInterval(this.blikInterval);
    
    this.blikInterval = setInterval(() => {
      this.blikTimeLeft.update(t => t - 1);
      if (this.blikTimeLeft() <= 0) {
        clearInterval(this.blikInterval);
        this.blikCode.set(null);
      }
    }, 1000);
  }

  submitTransfer() {
    if (this.transferForm.invalid) return;
    this.transferLoading.set(true);
    this.transferError.set('');

    const systemMap = { internal: 'INTERNAL', standard: 'ELIXIR', express: 'EXPRESS_ELIXIR', sorbnet: 'SORBNET' };
    const v = this.transferForm.value;
    const isInternal = this.selectedTransferType() === 'internal';

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
        this.transferForm.patchValue({ amount: '', account_number: '', title: '', recipient: '' });
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