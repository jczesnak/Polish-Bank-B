import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DecimalPipe, NgClass, NgIf, NgFor } from '@angular/common';
import { AuthService } from '../../core/services/auth.service';

interface Account {
  id: string;
  iban: string;
  balance: string;
  blocked_funds: string;
  available_balance: string;
  currency: string;
  account_type: string;
  account_type_display: string;
}

interface MockTransaction {
  title: string;
  category: string;
  system: string;
  amount: number;
  group: string;
  icon: string;
}

const MOCK_TRANSACTIONS: MockTransaction[] = [
  { title: 'Wypłata', category: 'Przychód', system: 'Elixir', amount: 12500, group: 'Dziś', icon: '💰' },
  { title: 'Coffee Corner', category: 'Jedzenie i picie', system: 'BLIK', amount: -24.5, group: 'Dziś', icon: '☕' },
  { title: 'Zakupy online', category: 'Zakupy', system: 'BLIK', amount: -459.99, group: 'Wczoraj', icon: '🛒' },
  { title: 'Czynsz', category: 'Mieszkanie', system: 'Sorbnet', amount: -3200, group: 'Wczoraj', icon: '🏠' },
  { title: 'Projekt freelance', category: 'Przychód', system: 'Express', amount: 5400, group: 'niedziela, 19 kwietnia', icon: '💼' },
  { title: 'Rachunek telefoniczny', category: 'Rachunki', system: 'Elixir', amount: -89, group: 'niedziela, 19 kwietnia', icon: '📱' },
];

const PAYMENT_SYSTEMS = [
  { name: 'Elixir Express', desc: 'Natychmiastowy • 24/7', icon: '⚡', color: 'text-yellow-400' },
  { name: 'Sorbnet', desc: 'Duże kwoty • Bezpieczny', icon: '🛡', color: 'text-blue-400' },
  { name: 'BLIK', desc: 'Mobilny • Natychmiastowy', icon: '📲', color: 'text-emerald-400' },
];

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [ReactiveFormsModule, DecimalPipe, NgClass, NgIf, NgFor],
  template: `
    <div class="min-h-screen bg-slate-950 text-white">

      <!-- Top nav -->
      <header class="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
            </svg>
          </div>
          <span class="font-bold text-lg tracking-tight">Polish Bank</span>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-slate-400 text-sm hidden sm:block">
            {{ user()?.first_name }} {{ user()?.last_name }}
          </span>
          <button (click)="logout()" class="btn-ghost text-sm py-2 px-3">
            Wyloguj
          </button>
        </div>
      </header>

      <main class="max-w-6xl mx-auto px-4 sm:px-6 py-8">

        <!-- Balance hero -->
        <div class="mb-8">
          <p class="text-xs font-semibold tracking-widest text-slate-500 uppercase mb-2">
            Całkowita płynność
          </p>
          <div class="flex items-end gap-4 mb-6">
            <h1 class="text-5xl font-bold tracking-tight">
              {{ totalBalance() | number:'1.0-2':'pl' }}
              <span class="text-2xl font-normal text-slate-400 ml-1">PLN</span>
            </h1>
            <span class="text-emerald-400 text-sm font-medium mb-2">+12.4% w tym miesiącu</span>
          </div>

          <!-- Quick actions -->
          <div class="grid grid-cols-3 gap-3">
            <button
              (click)="openTransferModal()"
              class="flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500
                     text-white font-medium py-3 px-4 rounded-xl transition-colors duration-200">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
              <span class="text-sm">Wyślij przelew</span>
            </button>
            <button class="flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700
                           text-slate-200 font-medium py-3 px-4 rounded-xl transition-colors duration-200">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
              <span class="text-sm">Generuj BLIK</span>
            </button>
            <button class="flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700
                           text-slate-200 font-medium py-3 px-4 rounded-xl transition-colors duration-200">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
              </svg>
              <span class="text-sm">Ustawienia kart</span>
            </button>
          </div>
        </div>

        <!-- Main grid -->
        <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">

          <!-- Transactions (left, wider) -->
          <div class="lg:col-span-3 card p-6">
            <h2 class="text-sm font-semibold tracking-wider text-slate-500 uppercase mb-5">
              Historia transakcji
            </h2>

            <div *ngFor="let group of transactionGroups()">
              <p class="text-xs text-slate-500 mb-3 mt-4 first:mt-0">{{ group.label }}</p>
              <div class="space-y-1">
                <div
                  *ngFor="let tx of group.items"
                  class="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-800/50 transition-colors cursor-pointer"
                >
                  <div class="w-9 h-9 bg-slate-800 rounded-lg flex items-center justify-center text-base flex-shrink-0">
                    {{ tx.icon }}
                  </div>
                  <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-white truncate">{{ tx.title }}</p>
                    <p class="text-xs text-slate-500">
                      {{ tx.category }}
                      <span class="mx-1">•</span>
                      <span>{{ tx.system }}</span>
                    </p>
                  </div>
                  <span
                    class="text-sm font-semibold flex-shrink-0"
                    [ngClass]="tx.amount > 0 ? 'text-emerald-400' : 'text-red-400'"
                  >
                    {{ tx.amount > 0 ? '+' : '' }}{{ tx.amount | number:'1.2-2':'pl' }}
                    <span class="text-xs font-normal text-slate-500 ml-0.5">PLN</span>
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Right column -->
          <div class="lg:col-span-2 space-y-6">

            <!-- Accounts -->
            <div class="card p-6">
              <h2 class="text-sm font-semibold tracking-wider text-slate-500 uppercase mb-4">
                Rachunki
              </h2>

              <div *ngIf="loadingAccounts()" class="space-y-3">
                <div *ngFor="let i of [1,2]" class="h-14 bg-slate-800 rounded-lg animate-pulse"></div>
              </div>

              <div *ngIf="!loadingAccounts()" class="space-y-3">
                <div
                  *ngFor="let acc of accounts()"
                  class="flex items-center justify-between p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <div>
                    <p class="text-sm font-medium text-white">{{ acc.account_type_display }}</p>
                    <p class="text-xs text-slate-500 mt-0.5">••••{{ acc.iban.slice(-4) }}</p>
                  </div>
                  <div class="text-right">
                    <p class="text-sm font-semibold text-white">
                      {{ acc.balance | number:'1.0-2':'pl' }}
                    </p>
                    <p class="text-xs text-slate-500">{{ acc.currency }}</p>
                  </div>
                </div>

                <div *ngIf="accounts().length === 0" class="text-slate-500 text-sm text-center py-4">
                  Brak rachunków
                </div>
              </div>
            </div>

            <!-- Payment systems -->
            <div class="card p-6">
              <h2 class="text-sm font-semibold tracking-wider text-slate-500 uppercase mb-4">
                Systemy płatności
              </h2>
              <div class="space-y-3">
                <div
                  *ngFor="let sys of paymentSystems"
                  class="flex items-center gap-3 p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <div class="w-9 h-9 bg-slate-900 border border-slate-700 rounded-lg
                               flex items-center justify-center text-base flex-shrink-0">
                    {{ sys.icon }}
                  </div>
                  <div>
                    <p class="text-sm font-medium text-white">{{ sys.name }}</p>
                    <p class="text-xs text-slate-500">{{ sys.desc }}</p>
                  </div>
                  <svg class="w-4 h-4 text-slate-600 ml-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>

          </div>
        </div>
      </main>
    </div>

    <!-- Transfer Modal -->
    <div
      *ngIf="showTransferModal()"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
    >
      <!-- Backdrop -->
      <div
        class="absolute inset-0 bg-black/70 backdrop-blur-sm"
        (click)="closeTransferModal()"
      ></div>

      <!-- Dialog -->
      <div class="relative w-full max-w-md card p-0 overflow-hidden z-10">

        <!-- Modal header -->
        <div class="px-6 py-5 border-b border-slate-800 flex items-start justify-between">
          <div>
            <h2 class="text-lg font-semibold text-white">Wyślij przelew</h2>
            <p class="text-sm text-slate-400 mt-0.5">Wybierz metodę przelewu i wprowadź dane</p>
          </div>
          <button
            (click)="closeTransferModal()"
            class="text-slate-500 hover:text-slate-300 transition-colors p-1 -mt-1 -mr-1"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Transfer type tabs -->
        <div class="px-6 pt-5">
          <div class="flex bg-slate-800 rounded-xl p-1 gap-1">
            <button
              *ngFor="let t of transferTypes"
              (click)="selectedTransferType.set(t.key)"
              class="flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-sm font-medium transition-all duration-200"
              [ngClass]="selectedTransferType() === t.key ? 'tab-active' : 'tab-inactive'"
            >
              {{ t.label }}
            </button>
          </div>

          <!-- Selected type info box -->
          <div class="mt-4 bg-slate-800/50 border border-slate-700 rounded-xl p-4">
            <div class="flex items-center gap-3 mb-3">
              <div class="w-9 h-9 bg-slate-700 rounded-lg flex items-center justify-center">
                🛡
              </div>
              <div>
                <p class="text-sm font-semibold text-white">{{ selectedTypeInfo().name }}</p>
                <p class="text-xs text-slate-400">{{ selectedTypeInfo().desc }}</p>
              </div>
            </div>
            <div class="grid grid-cols-3 gap-3 text-xs">
              <div>
                <p class="text-slate-500 mb-0.5">Czas realizacji</p>
                <p class="text-white font-medium">{{ selectedTypeInfo().time }}</p>
              </div>
              <div>
                <p class="text-slate-500 mb-0.5">Opłata</p>
                <p class="text-white font-medium">{{ selectedTypeInfo().fee }}</p>
              </div>
              <div>
                <p class="text-slate-500 mb-0.5">Limit dzienny</p>
                <p class="text-white font-medium text-indigo-400">{{ selectedTypeInfo().limit }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Form -->
        <form [formGroup]="transferForm" (ngSubmit)="submitTransfer()" class="px-6 pb-6 pt-4 space-y-4">
          <div>
            <label class="label">Kwota</label>
            <div class="relative">
              <input
                formControlName="amount"
                type="number"
                step="0.01"
                min="0.01"
                class="input-field pr-14"
                placeholder="0.00"
              />
              <span class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm font-medium">
                PLN
              </span>
            </div>
          </div>

          <div>
            <label class="label">Odbiorca</label>
            <input
              formControlName="recipient"
              type="text"
              class="input-field"
              placeholder="Jan Kowalski"
            />
          </div>

          <div>
            <label class="label">Numer rachunku</label>
            <input
              formControlName="account_number"
              type="text"
              class="input-field font-mono tracking-wider"
              placeholder="PL 1234 5678 9012 3456 7890 1234"
            />
          </div>

          <div>
            <label class="label">Tytuł przelewu</label>
            <input
              formControlName="title"
              type="text"
              class="input-field"
              placeholder="Opłata za usługi"
            />
          </div>

          <div *ngIf="transferError()" class="p-3 bg-red-950/60 border border-red-900 rounded-lg text-red-400 text-sm">
            {{ transferError() }}
          </div>

          <button
            type="submit"
            [disabled]="transferLoading() || transferForm.invalid"
            class="btn-primary w-full flex items-center justify-center gap-2 py-3 mt-2"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
            {{ transferLoading() ? 'Wysyłanie...' : 'Wyślij przelew' }}
          </button>
        </form>
      </div>
    </div>
  `,
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  private auth = inject(AuthService);
  private fb = inject(FormBuilder);

  readonly user = this.auth.user;
  accounts = signal<Account[]>([]);
  loadingAccounts = signal(true);
  showTransferModal = signal(false);
  selectedTransferType = signal<'standard' | 'express' | 'sorbnet'>('standard');
  transferLoading = signal(false);
  transferError = signal('');

  readonly paymentSystems = PAYMENT_SYSTEMS;

  readonly transferTypes = [
    { key: 'standard' as const, label: 'Standardowy' },
    { key: 'express' as const, label: 'Express' },
    { key: 'sorbnet' as const, label: 'Sorbnet' },
  ];

  readonly selectedTypeInfo = computed(() => {
    const map = {
      standard: {
        name: 'Elixir Standardowy',
        desc: 'Standardowy przelew krajowy z rozliczeniem następnego dnia roboczego',
        time: '1-2 dni robocze',
        fee: 'Bezpłatny',
        limit: '100 000 PLN',
      },
      express: {
        name: 'Express Elixir',
        desc: 'Natychmiastowy przelew krajowy dostępny 24/7/365',
        time: 'Do 10 sekund',
        fee: 'Bezpłatny',
        limit: '100 000 PLN',
      },
      sorbnet: {
        name: 'SORBNET3',
        desc: 'Przelew wysokokwotowy RTGS przez Narodowy Bank Polski',
        time: 'Natychmiast (RTGS)',
        fee: '1 PLN',
        limit: 'Bez limitu',
      },
    };
    return map[this.selectedTransferType()];
  });

  readonly totalBalance = computed(() =>
    this.accounts().reduce((sum, acc) => sum + parseFloat(acc.balance), 0),
  );

  readonly transactionGroups = computed(() => {
    const map = new Map<string, MockTransaction[]>();
    MOCK_TRANSACTIONS.forEach((tx) => {
      if (!map.has(tx.group)) map.set(tx.group, []);
      map.get(tx.group)!.push(tx);
    });
    return Array.from(map.entries()).map(([label, items]) => ({ label, items }));
  });

  transferForm = this.fb.group({
    amount: ['', [Validators.required, Validators.min(0.01)]],
    recipient: ['', Validators.required],
    account_number: ['', Validators.required],
    title: ['', Validators.required],
  });

  ngOnInit() {
    this.http.get<Account[]>('/api/accounts/').subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        this.loadingAccounts.set(false);
      },
      error: () => this.loadingAccounts.set(false),
    });
  }

  logout() {
    this.auth.logout();
  }

  openTransferModal() {
    this.showTransferModal.set(true);
    this.transferError.set('');
    this.transferForm.reset();
  }

  closeTransferModal() {
    this.showTransferModal.set(false);
  }

  submitTransfer() {
    if (this.transferForm.invalid || !this.accounts().length) return;
    this.transferLoading.set(true);
    this.transferError.set('');

    const systemMap = { standard: 'ELIXIR', express: 'EXPRESS_ELIXIR', sorbnet: 'SORBNET' };
    const payload = {
      sender_account: this.accounts()[0].id,
      recipient_iban: (this.transferForm.value['account_number'] as string).replace(/\s/g, ''),
      recipient_name: this.transferForm.value['recipient'],
      amount: this.transferForm.value['amount'],
      title: this.transferForm.value['title'],
      system_route: systemMap[this.selectedTransferType()],
    };

    this.http.post('/api/transfers/', payload).subscribe({
      next: () => {
        this.transferLoading.set(false);
        this.closeTransferModal();
        this.ngOnInit();
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
