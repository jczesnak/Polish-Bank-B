import { CommonModule, NgClass, DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { catchError, of } from 'rxjs';
import { JuniorBlikTransaction, JuniorService, BankAccount, PrepaidCard } from '../../core/services/junior.service';
import { LookupResult, P2pContact, P2pService } from '../../core/services/p2p.service';
import { TransferService } from '../../core/services/transfer.service';

type PaymentTab = 'internet' | 'blik' | 'transfer';
type TransferTab = 'iban' | 'phone';
type InternetMethod = 'card' | 'blik';

@Component({
  selector: 'app-junior-payments',
  standalone: true,
  imports: [CommonModule, NgClass, ReactiveFormsModule, RouterLink, DatePipe],
  templateUrl: './junior-payments.component.html',
})
export class JuniorPaymentsComponent implements OnInit, OnDestroy {
  private fb = inject(FormBuilder);
  private http = inject(HttpClient);
  private junior = inject(JuniorService);
  private p2p = inject(P2pService);
  private transfers = inject(TransferService);

  account = signal<BankAccount | null>(null);
  card = signal<PrepaidCard | null>(null);
  contacts = signal<P2pContact[]>([]);
  lookupResult = signal<LookupResult | null>(null);
  blikTransactions = signal<JuniorBlikTransaction[]>([]);
  activeTab = signal<PaymentTab>('internet');
  internetMethod = signal<InternetMethod>('card');
  transferTab = signal<TransferTab>('iban');
  blikCode = signal<string | null>(null);
  blikTimeLeft = signal(0);
  blikLoading = signal(false);
  blikHistoryLoading = signal(false);
  p2pLoading = signal(false);
  lookupLoading = signal(false);
  message = signal('');
  error = signal('');
  private blikInterval: ReturnType<typeof setInterval> | null = null;
  private blikPollInterval: ReturnType<typeof setInterval> | null = null;
  private blikTxCountAtGenerate = 0;

  cardForm = this.fb.group({
    merchant_name: ['', Validators.required],
    amount: ['', [Validators.required, Validators.min(0.01)]],
  });

  transferForm = this.fb.group({
    recipient_iban: ['', [Validators.required, Validators.minLength(26)]],
    recipient_name: ['', Validators.required],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    title: ['Przelew Junior', Validators.required],
  });

  p2pForm = this.fb.group({
    recipient_phone: ['', [Validators.required, Validators.minLength(9)]],
    recipient_name: [''],
    save_contact: [false],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    title: ['Przelew na telefon', Validators.required],
  });

  readonly tabs: { key: PaymentTab; label: string; emoji: string }[] = [
    { key: 'internet', label: 'Internet', emoji: '🛒' },
    { key: 'blik', label: 'BLIK', emoji: '🎲' },
    { key: 'transfer', label: 'Przelew', emoji: '💸' },
  ];

  ngOnInit() {
    this.load();
    this.loadContacts();
    this.loadBlikTransactions();
  }

  ngOnDestroy() {
    this.clearBlikTimers();
  }

  load() {
    this.junior.listAccounts().subscribe((accounts) => {
      this.account.set(accounts.find((a) => a.account_type === 'JUNIOR') || null);
    });
    this.junior.listCards().subscribe((cards) => this.card.set(cards[0] || null));
  }

  loadContacts() {
    this.p2p.listContacts().subscribe((contacts) => this.contacts.set(contacts));
  }

  loadBlikTransactions() {
    this.blikHistoryLoading.set(true);
    this.http.get<JuniorBlikTransaction[]>('/api/blik/transactions/').pipe(
      catchError(() => of([])),
    ).subscribe((txs) => {
      this.blikTransactions.set(txs);
      this.blikHistoryLoading.set(false);
      this.checkBlikPaymentCompleted(txs);
    });
  }

  setTab(tab: PaymentTab) {
    this.activeTab.set(tab);
    this.message.set('');
    this.error.set('');
    if (tab === 'blik' || tab === 'internet') {
      this.loadBlikTransactions();
    }
  }

  setInternetMethod(method: InternetMethod) {
    this.internetMethod.set(method);
    this.message.set('');
    this.error.set('');
    if (method === 'blik') {
      this.loadBlikTransactions();
    }
  }

  selectContact(contact: P2pContact) {
    this.transferTab.set('phone');
    this.p2pForm.patchValue({
      recipient_phone: contact.phone,
      recipient_name: contact.name,
    });
    this.lookupResult.set(null);
  }

  checkNumber() {
    const phone = this.p2pForm.value.recipient_phone || '';
    if (!phone) return;
    this.lookupLoading.set(true);
    this.lookupResult.set(null);
    this.p2p.lookup(phone).subscribe({
      next: (res) => {
        this.lookupResult.set(res);
        this.lookupLoading.set(false);
      },
      error: () => {
        this.lookupLoading.set(false);
        this.lookupResult.set(null);
      },
    });
  }

  submitCardPayment() {
    const card = this.card();
    if (!card || this.cardForm.invalid) {
      this.cardForm.markAllAsTouched();
      return;
    }
    this.clearAlerts();
    this.junior.cardPayment(card.id, {
      merchant_name: this.cardForm.value.merchant_name as string,
      amount: Number(this.cardForm.value.amount || 0).toFixed(2),
      transaction_type: 'INTERNET',
    }).subscribe({
      next: () => {
        this.message.set('Płatność wysłana do akceptacji rodzica.');
        this.cardForm.patchValue({ merchant_name: '', amount: '' });
      },
      error: (err) => this.error.set(this.extractError(err, 'Nie udało się utworzyć płatności.')),
    });
  }

  generateBlik() {
    const account = this.account();
    if (!account) return;
    this.clearBlikTimers();
    this.clearAlerts();
    this.blikCode.set(null);
    this.blikLoading.set(true);
    this.blikTxCountAtGenerate = this.blikTransactions().length;

    this.http.post<{ code: string; expires_in: number }>('/api/blik/generate/', { account_id: account.id }).subscribe({
      next: (res) => {
        this.blikCode.set(res.code);
        this.blikTimeLeft.set(res.expires_in ?? 120);
        this.blikLoading.set(false);
        this.message.set('Podaj ten kod w sklepie lub terminalu. Rodzic zatwierdzi płatność po jej zainicjowaniu.');
        this.blikInterval = setInterval(() => {
          this.blikTimeLeft.update((time) => Math.max(time - 1, 0));
          if (this.blikTimeLeft() <= 0) {
            this.clearBlikCodeTimer();
            this.blikCode.set(null);
          }
        }, 1000);
        this.blikPollInterval = setInterval(() => this.loadBlikTransactions(), 4000);
      },
      error: (err) => {
        this.blikLoading.set(false);
        this.error.set(this.extractError(err, 'Nie udało się wygenerować BLIK.'));
      },
    });
  }

  blikStatusLabel(status: string) {
    switch (status) {
      case 'COMPLETED': return 'Zrealizowana';
      case 'PENDING': return 'Czeka na zgodę rodzica';
      case 'REJECTED': return 'Odrzucona';
      default: return status;
    }
  }

  submitTransfer() {
    const account = this.account();
    if (!account || this.transferForm.invalid) {
      this.transferForm.markAllAsTouched();
      return;
    }
    this.clearAlerts();
    this.transfers.createInternalTransfer({
      sender_account: account.id,
      ...this.transferForm.value,
    }).subscribe({
      next: () => {
        this.message.set('Przelew wysłany do akceptacji rodzica.');
        this.transferForm.patchValue({
          recipient_iban: '',
          recipient_name: '',
          amount: '',
          title: 'Przelew Junior',
        });
      },
      error: (err) => this.error.set(this.extractError(err, 'Nie udało się wysłać przelewu.')),
    });
  }

  submitP2pTransfer() {
    const account = this.account();
    if (!account || this.p2pForm.invalid) {
      this.p2pForm.markAllAsTouched();
      return;
    }
    this.clearAlerts();
    this.p2pLoading.set(true);

    const v = this.p2pForm.value;
    this.p2p.transfer({
      sender_account: account.id,
      recipient_phone: v.recipient_phone as string,
      recipient_name: (v.recipient_name as string) || undefined,
      save_contact: !!v.save_contact,
      amount: parseFloat((v.amount as string) || '0').toFixed(2),
      title: v.title as string,
    }).subscribe({
      next: (res) => {
        this.p2pLoading.set(false);
        const who = res.recipient_name || res.recipient_phone;
        this.message.set(`Przelew ${res.amount} PLN do ${who} czeka na zgodę rodzica.`);
        if (res.contact_saved) this.loadContacts();
        this.p2pForm.patchValue({
          recipient_phone: '',
          recipient_name: '',
          amount: '',
          save_contact: false,
          title: 'Przelew na telefon',
        });
        this.lookupResult.set(null);
      },
      error: (err) => {
        this.p2pLoading.set(false);
        this.error.set(this.extractError(err, 'Nie udało się wysłać przelewu na telefon.'));
      },
    });
  }

  private checkBlikPaymentCompleted(txs: JuniorBlikTransaction[]) {
    if (!this.blikCode() && !this.blikPollInterval) return;
    if (txs.length <= this.blikTxCountAtGenerate) return;

    const latest = txs[0];
    if (!latest) return;

    if (latest.status === 'COMPLETED') {
      this.message.set(`Płatność BLIK ${latest.amount} PLN zrealizowana${latest.merchant_name ? ' — ' + latest.merchant_name : ''}.`);
      this.clearBlikTimers();
      this.blikCode.set(null);
    } else if (latest.status === 'PENDING') {
      this.message.set(`Płatność BLIK ${latest.amount} PLN czeka na zgodę rodzica.`);
    } else if (latest.status === 'REJECTED') {
      this.error.set('Płatność BLIK została odrzucona.');
      this.clearBlikTimers();
      this.blikCode.set(null);
    }
  }

  private clearBlikCodeTimer() {
    if (this.blikInterval) {
      clearInterval(this.blikInterval);
      this.blikInterval = null;
    }
  }

  private clearBlikTimers() {
    this.clearBlikCodeTimer();
    if (this.blikPollInterval) {
      clearInterval(this.blikPollInterval);
      this.blikPollInterval = null;
    }
  }

  private clearAlerts() {
    this.message.set('');
    this.error.set('');
  }

  private extractError(err: any, fallback: string) {
    const data = err?.error;
    if (data?.detail) return data.detail;
    if (typeof data === 'object' && data) return Object.values(data).flat().join(' ');
    return fallback;
  }
}
