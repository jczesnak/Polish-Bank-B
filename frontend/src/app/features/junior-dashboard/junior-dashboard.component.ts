import { Component, OnInit, OnDestroy, signal, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../core/services/auth.service';
import { DecimalPipe, NgIf, NgFor, NgClass, DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { NotificationService } from '../../core/services/notification.service';
import { forkJoin } from 'rxjs';

interface BlikTransaction {
  id: string;
  amount: string;
  currency: string;
  merchant_name: string;
  status: string;
  needs_parent_auth: boolean;
  created_at: string;
}

interface CardTransaction {
  id: string;
  card: number;
  amount: string;
  currency: string;
  merchant_name: string;
  status: string;
  created_at: string;
}

interface TransferRequest {
  id: number;
  amount: string;
  recipient_iban: string;
  recipient_name: string;
  title: string;
  system_route: string;
  status: string;
  status_display: string;
  created_at: string;
}

interface HistoryEntry {
  id: string;
  amount: string;
  currency: string;
  merchant_name?: string;
  recipient_name?: string;
  recipient_iban?: string;
  title?: string;
  status: string;
  created_at: string;
  type: 'blik' | 'card' | 'transfer_out' | 'transfer_in';
}

@Component({
  selector: 'app-junior-dashboard',
  standalone: true,
  imports: [NgIf, NgFor, NgClass, DecimalPipe, DatePipe, ReactiveFormsModule],
  templateUrl: './junior-dashboard.component.html',
  styleUrl: './junior-dashboard.component.css'
})
export class JuniorDashboardComponent implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  public auth = inject(AuthService);
  public notifSvc = inject(NotificationService);
  private fb = inject(FormBuilder);

  user = this.auth.user;
  account = signal<any>(null);
  card = signal<any>(null);
  cardDetails = signal<any>(null);
  cardDetailsLoading = signal(false);
  cardDetailsError = signal('');
  showCardDetails = signal(false);

  history = signal<HistoryEntry[]>([]);
  loadingHistory = signal(false);

  showNotifications = signal(false);

  blikCode = signal<string | null>(null);
  blikTimeLeft = signal(0);
  blikLoading = signal(false);
  blikError = signal('');
  blikInterval: any;

  pendingBlikTx = signal<BlikTransaction | null>(null);
  blikPinForm = this.fb.group({ pin: ['', [Validators.required, Validators.pattern('^[0-9]{4}$')]] });
  blikPinLoading = signal(false);
  blikPinError = signal('');

  setPinForm = this.fb.group({
    pin: ['', [Validators.required, Validators.pattern('^[0-9]{4}$')]],
    pin_confirm: ['', [Validators.required, Validators.pattern('^[0-9]{4}$')]],
  });
  setPinLoading = signal(false);
  setPinError = signal('');
  setPinSuccess = signal(false);

  // Transfer requests
  showTransferModal = signal(false);
  transferLoading = signal(false);
  transferError = signal('');
  transferSuccess = signal('');
  transferRequests = signal<TransferRequest[]>([]);
  loadingTransferRequests = signal(false);
  retryData = signal<Partial<TransferRequest> | null>(null);

  transferForm = this.fb.group({
    amount: ['', [Validators.required, Validators.min(0.01)]],
    // IBAN dopuszcza spacje (np. wklejony "PL00 0000 ..."); usuwamy je przy wysyłce.
    recipient_iban: ['', [Validators.required, Validators.pattern('^[A-Z]{2}[0-9]{2}[A-Z0-9 ]{1,38}$')]],
    recipient_name: ['', Validators.required],
    title: ['', Validators.required],
    system_route: ['ELIXIR', Validators.required],
  });

  pollingInterval: any;

  ngOnInit() {
    this.loadData();
    this.loadHistory();
    this.loadTransferRequests();
    this.pollingInterval = setInterval(() => {
      this.pollPendingBlik();
      this.loadTransferRequests();
    }, 5000);
  }

  ngOnDestroy() {
    if (this.blikInterval) clearInterval(this.blikInterval);
    if (this.pollingInterval) clearInterval(this.pollingInterval);
  }

  loadData() {
    this.http.get<any[]>('/api/accounts/').subscribe({
      next: (accounts) => { if (accounts.length > 0) this.account.set(accounts[0]); }
    });
    this.http.get<any[]>('/api/cards/my-cards/').subscribe({
      next: (cards) => { if (cards.length > 0) this.card.set(cards[0]); }
    });
  }

  loadHistory() {
    this.loadingHistory.set(true);
    forkJoin({
      blik: this.http.get<BlikTransaction[]>('/api/blik/transactions/'),
      cards: this.http.get<CardTransaction[]>('/api/cards/transactions/'),
      transfersOut: this.http.get<any[]>('/api/transfers/'),
      transfersIn: this.http.get<any[]>('/api/transfers/incoming/'),
    }).subscribe({
      next: ({ blik, cards, transfersOut, transfersIn }) => {
        const blikEntries: HistoryEntry[] = blik.map(t => ({ ...t, type: 'blik' as const }));
        const cardEntries: HistoryEntry[] = cards.map(t => ({ ...t, type: 'card' as const }));
        const outEntries: HistoryEntry[] = transfersOut.map(t => ({
          id: t.id, amount: t.amount, currency: 'PLN',
          recipient_name: t.recipient_name, recipient_iban: t.recipient_iban,
          title: t.title, status: t.status, created_at: t.created_at,
          type: 'transfer_out' as const,
        }));
        const inEntries: HistoryEntry[] = transfersIn.map(t => ({
          id: t.id, amount: t.amount, currency: 'PLN',
          recipient_name: t.sender_name, title: t.title,
          status: t.status, created_at: t.created_at,
          type: 'transfer_in' as const,
        }));
        const merged = [...blikEntries, ...cardEntries, ...outEntries, ...inEntries]
          .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        this.history.set(merged);
        this.loadingHistory.set(false);
      },
      error: () => this.loadingHistory.set(false)
    });
  }

  pollPendingBlik() {
    this.http.get<BlikTransaction[]>('/api/blik/transactions/').subscribe({
      next: (txs) => {
        const pending = txs.find(t => t.status === 'PENDING' && !t.needs_parent_auth);
        if (pending && !this.pendingBlikTx()) {
          this.pendingBlikTx.set(pending);
          this.blikPinForm.reset();
          this.blikPinError.set('');
          this.notifSvc.add(`Oczekująca płatność BLIK: ${pending.amount} PLN`, 'out');
        } else if (!pending) {
          this.pendingBlikTx.set(null);
        }
      }
    });
  }

  authorizeBlik() {
    if (this.blikPinForm.invalid || !this.pendingBlikTx()) return;
    this.blikPinLoading.set(true);
    this.blikPinError.set('');
    this.http.post(`/api/blik/transactions/${this.pendingBlikTx()?.id}/authorize/`, this.blikPinForm.value).subscribe({
      next: () => {
        this.blikPinLoading.set(false);
        this.pendingBlikTx.set(null);
        this.loadData();
        this.loadHistory();
      },
      error: (err) => {
        this.blikPinLoading.set(false);
        this.blikPinError.set(err.error?.pin || err.error?.detail || 'Błąd autoryzacji. Sprawdź PIN.');
      }
    });
  }

  rejectBlik() {
    if (!this.pendingBlikTx()) return;
    this.blikPinLoading.set(true);
    this.http.post(`/api/blik/transactions/${this.pendingBlikTx()?.id}/reject/`, {}).subscribe({
      next: () => {
        this.blikPinLoading.set(false);
        this.pendingBlikTx.set(null);
        this.loadHistory();
      },
      error: () => { this.blikPinLoading.set(false); }
    });
  }

  generateBlik() {
    const acc = this.account();
    if (!acc) return;
    this.blikLoading.set(true);
    this.blikError.set('');
    this.http.post<{ code: string; expires_in: number }>('/api/blik/generate/', { account_id: acc.id }).subscribe({
      next: (res) => {
        this.blikCode.set(res.code);
        this.blikTimeLeft.set(res.expires_in ?? 120);
        this.blikLoading.set(false);
        if (this.blikInterval) clearInterval(this.blikInterval);
        this.blikInterval = setInterval(() => {
          this.blikTimeLeft.update(t => t - 1);
          if (this.blikTimeLeft() <= 0) { clearInterval(this.blikInterval); this.blikCode.set(null); }
        }, 1000);
      },
      error: (err) => {
        this.blikLoading.set(false);
        this.blikError.set(err?.error?.detail ?? 'Nie udało się wygenerować kodu.');
      }
    });
  }

  copyBlikCode() {
    const code = this.blikCode();
    if (code) navigator.clipboard.writeText(code).then(() => this.notifSvc.add('Skopiowano kod BLIK!', 'in'));
  }

  toggleCardDetails() {
    if (this.showCardDetails()) { this.showCardDetails.set(false); return; }
    const c = this.card();
    if (!c) return;
    if (this.cardDetails()) { this.showCardDetails.set(true); return; }
    this.cardDetailsLoading.set(true);
    this.cardDetailsError.set('');
    this.http.get<any>(`/api/cards/${c.id}/details/`).subscribe({
      next: (res) => { this.cardDetails.set(res); this.cardDetailsLoading.set(false); this.showCardDetails.set(true); },
      error: () => { this.cardDetailsLoading.set(false); this.cardDetailsError.set('Nie udało się pobrać danych karty.'); }
    });
  }

  setPin() {
    const { pin, pin_confirm } = this.setPinForm.value;
    if (pin !== pin_confirm) { this.setPinError.set('Kody PIN nie są takie same.'); return; }
    this.setPinLoading.set(true);
    this.setPinError.set('');
    this.setPinSuccess.set(false);
    this.http.post('/api/auth/pin/', { pin }).subscribe({
      next: () => {
        this.setPinLoading.set(false);
        this.setPinSuccess.set(true);
        this.setPinForm.reset();
        setTimeout(() => this.setPinSuccess.set(false), 3000);
      },
      error: (err) => {
        this.setPinLoading.set(false);
        this.setPinError.set(err?.error?.pin || err?.error?.detail || 'Wystąpił błąd.');
      }
    });
  }

  loadTransferRequests() {
    this.loadingTransferRequests.set(true);
    this.http.get<TransferRequest[]>('/api/accounts/junior/transfer-requests/my/').subscribe({
      next: (data) => { this.transferRequests.set(data); this.loadingTransferRequests.set(false); },
      error: () => this.loadingTransferRequests.set(false),
    });
  }

  openTransferModal(prefill?: Partial<TransferRequest>) {
    // reset() bez wartości wyzerowałby system_route do null (pole required),
    // przez co formularz zostawał niepoprawny i przycisk był wyłączony.
    this.transferForm.reset({ system_route: 'ELIXIR' });
    this.transferError.set('');
    this.transferSuccess.set('');
    if (prefill) {
      this.transferForm.patchValue({
        amount: prefill.amount ?? '',
        recipient_iban: prefill.recipient_iban ?? '',
        recipient_name: prefill.recipient_name ?? '',
        title: prefill.title ?? '',
        system_route: prefill.system_route ?? 'ELIXIR',
      });
    }
    this.showTransferModal.set(true);
  }

  closeTransferModal() {
    this.showTransferModal.set(false);
    this.transferForm.reset();
  }

  submitTransfer() {
    if (this.transferForm.invalid) return;
    this.transferLoading.set(true);
    this.transferError.set('');
    this.transferSuccess.set('');
    const payload = {
      ...this.transferForm.value,
      recipient_iban: (this.transferForm.value.recipient_iban ?? '').replace(/\s/g, ''),
    };
    this.http.post<TransferRequest>('/api/accounts/junior/transfer-requests/', payload).subscribe({
      next: () => {
        this.transferLoading.set(false);
        this.transferSuccess.set('Wniosek wysłany! Czeka na zatwierdzenie rodzica.');
        this.loadTransferRequests();
        this.transferForm.reset();
        setTimeout(() => this.closeTransferModal(), 2000);
      },
      error: (err) => {
        this.transferLoading.set(false);
        const data = err?.error;
        if (typeof data === 'object') {
          this.transferError.set(Object.values(data).flat().join(' '));
        } else {
          this.transferError.set('Błąd wysyłania wniosku.');
        }
      },
    });
  }

  requestStatusClass(status: string): string {
    if (status === 'APPROVED') return 'text-green-600';
    if (status === 'REJECTED') return 'text-red-500';
    return 'text-yellow-500';
  }

  statusLabel(status: string): string {
    const map: Record<string, string> = {
      PENDING: 'Oczekuje', COMPLETED: 'Zrealizowana', REJECTED: 'Odrzucona', FAILED: 'Nieudana',
      AUTHORIZED: 'Autoryzowana', SETTLED: 'Rozliczona', REFUNDED: 'Zwrot',
    };
    return map[status] ?? status;
  }

  statusClass(status: string): string {
    if (status === 'COMPLETED' || status === 'SETTLED') return 'text-green-600';
    if (status === 'REJECTED' || status === 'FAILED') return 'text-red-500';
    if (status === 'REFUNDED') return 'text-blue-500';
    return 'text-yellow-500';
  }

  logout() { this.auth.logout(); }
}
