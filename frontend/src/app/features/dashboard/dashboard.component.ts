import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { DecimalPipe, NgClass, NgIf, NgFor, DatePipe, SlicePipe } from '@angular/common';
import { forkJoin, catchError, of } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { CardService } from '../../core/services/card.service';

export interface BlikTransaction {
  id: string;
  klik_transaction_id: string;
  amount: string;
  currency: string;
  merchant_name: string;
  status: string;
  reject_reason: string;
  created_at: string;
  completed_at: string | null;
}

export interface Account { id: string; iban: string; balance: string; blocked_funds: string; available_balance: string; currency: string; account_type: string; account_type_display: string; }

export interface Transfer {
  id: string;
  sender_iban?: string;
  sender_name?: string;
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
  imports: [ReactiveFormsModule, RouterLink, DecimalPipe, NgClass, NgIf, NgFor, DatePipe, SlicePipe],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  public auth = inject(AuthService);
  private fb = inject(FormBuilder);
  private notifSvc = inject(NotificationService);
  private cardService = inject(CardService);

  user = this.auth.user;
  accounts = signal<Account[]>([]);
  transfers = signal<Transfer[]>([]);
  blikTransactions = signal<BlikTransaction[]>([]);
  
  // Stan Kart
  cards = signal<any[]>([]);
  loadingCards = signal(false);
  currentCardIndex = signal(0);

  nextCard() {
    const len = this.cards().length;
    if (len <= 1) return;
    this.currentCardIndex.update(i => (i + 1) % len);
  }

  prevCard() {
    const len = this.cards().length;
    if (len <= 1) return;
    this.currentCardIndex.update(i => (i - 1 + len) % len);
  }

  goToCard(index: number) {
    if (index >= 0 && index < this.cards().length) {
      this.currentCardIndex.set(index);
    }
  }


  showDetailsModal = signal(false);
  selectedCardDetails = signal<any>(null);

  showOrderCardModal = signal(false);

  loadingAccounts = signal(true);
  loadingTransfers = signal(true);
  loadingBlik = signal(true);
  private previousBalance = -1;

  // Stan Modali
  showTransferModal = signal(false);
  showBlikModal = signal(false);

  selectedTransferType = signal<'internal' | 'standard' | 'express' | 'sorbnet'>('internal');
  transferLoading = signal(false);
  transferError = signal('');

  blikCode = signal<string | null>(null);
  blikTimeLeft = signal<number>(0);
  blikInterval: any;
  blikLoading = signal(false);
  blikError = signal('');
  blikConfirmed = signal(false);

  historyFilter = signal<'all' | 'out' | 'in'>('all');

  readonly historyFilters = [
    { key: 'all' as const, label: 'Wszystkie' },
    { key: 'out' as const, label: 'Wychodzące' },
    { key: 'in' as const, label: 'Przychodzące' },
  ];

  readonly filteredTransfers = computed(() => {
    const f = this.historyFilter();
    const all = this.transfers();
    if (f === 'all') return all;
    return all.filter(t => t.direction === (f === 'in' ? 'IN' : 'OUT'));
  });

  readonly historyCounts = computed(() => {
    const all = this.transfers();
    return {
      all: all.length,
      out: all.filter(t => t.direction === 'OUT').length,
      in: all.filter(t => t.direction === 'IN').length,
    };
  });

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

  readonly wydatki = computed(() =>
    this.transfers().filter(t => t.direction === 'OUT')
      .reduce((sum, t) => sum + parseFloat(t.amount), 0)
  );

  readonly wplywy = computed(() =>
    this.transfers().filter(t => t.direction === 'IN')
      .reduce((sum, t) => sum + parseFloat(t.amount), 0)
  );

  readonly balanceChartData = computed(() => {
    const sorted = [...this.transfers()]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const current = this.totalBalance();
    const points: { label: string; balance: number }[] = [
      { label: 'Teraz', balance: current },
    ];

    let running = current;
    for (const t of sorted.slice(0, 7)) {
      running += t.direction === 'OUT' ? parseFloat(t.amount) : -parseFloat(t.amount);
      const d = new Date(t.created_at);
      points.push({
        label: d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }),
        balance: Math.max(0, running),
      });
    }

    const reversed = points.reverse();
    const maxBal = Math.max(...reversed.map(p => p.balance), 1);

    return reversed.map(p => ({
      label: p.label,
      balance: p.balance,
      balanceStr: p.balance.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
      heightPct: Math.max(Math.round((p.balance / maxBal) * 100), 5),
      isCurrent: p.label === 'Teraz',
    }));
  });

  readonly minBalance = computed(() => {
    const d = this.balanceChartData();
    return d.length > 0 ? Math.min(...d.map(p => p.balance)) : 0;
  });

  readonly maxBalance = computed(() => {
    const d = this.balanceChartData();
    return d.length > 0 ? Math.max(...d.map(p => p.balance)) : 0;
  });

  transferForm = this.fb.group({
    sender_account: [''],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    recipient: [''],
    account_number: ['', Validators.required],
    title: ['', Validators.required],
  });

  orderCardForm = this.fb.group({
    card_type: ['VIRTUAL', Validators.required],
    initial_balance: [0, [Validators.min(0)]],
  });

  ngOnInit() {
    this.loadAccounts();
    this.loadTransfers();
    this.loadBlikTransactions();
    this.loadCards();
  }

  // --- Obsługa Kart ---
  loadCards() {
    this.loadingCards.set(true);
    this.cardService.getCards().subscribe({
      next: (res) => {
        this.cards.set(res);
        if (this.currentCardIndex() >= res.length && res.length > 0) {
          this.currentCardIndex.set(res.length - 1);
        } else if (res.length === 0) {
          this.currentCardIndex.set(0);
        }
        this.loadingCards.set(false);
      },
      error: () => this.loadingCards.set(false)
    });
  }

  openDetails(card: any) {
    this.cardService.getCardDetails(card.id).subscribe({
      next: (res) => {
        this.selectedCardDetails.set({
          ...res,
          id: card.id,
          is_active: card.is_active,
          name: `${this.user()?.first_name} ${this.user()?.last_name}`
        });
        this.showDetailsModal.set(true);
      },
      error: () => this.notifSvc.add('Błąd pobierania danych karty', 'out')
    });
  }

  openOrderCardModal() {
    this.orderCardForm.reset({ card_type: 'VIRTUAL', initial_balance: 0 });
    this.showOrderCardModal.set(true);
  }

  closeOrderCardModal() {
    this.showOrderCardModal.set(false);
  }

  onOrderCard() {
    if (this.orderCardForm.invalid) return;
    const vals = this.orderCardForm.value;
    
    this.cardService.orderCard(vals.card_type || 'VIRTUAL', vals.initial_balance || 0).subscribe({
      next: () => {
        this.notifSvc.add('Karta została zamówiona!', 'in');
        this.closeOrderCardModal();
        this.loadCards();
      },
      error: (err) => this.notifSvc.add(err.error?.error || 'Błąd zamawiania karty', 'out')
    });
  }

  onToggleCardBlock(card: any) {
    if (card.is_active) {
      if(!confirm('Czy na pewno chcesz zawiesić tę kartę?')) return;
      this.cardService.blockCard(card.id).subscribe({
        next: () => {
          this.notifSvc.add('Karta została zawieszona', 'out');
          this.loadCards();
        },
        error: (err) => this.notifSvc.add(err.error?.error || 'Błąd zawieszania', 'out')
      });
    } else {
      if(!confirm('Czy na pewno chcesz odblokować tę kartę?')) return;
      this.cardService.unblockCard(card.id).subscribe({
        next: () => {
          this.notifSvc.add('Karta została odblokowana', 'in');
          this.loadCards();
        },
        error: (err) => this.notifSvc.add(err.error?.error || 'Błąd odblokowania', 'out')
      });
    }
  }

  onDeleteCard(cardId: number) {
    if(!confirm('Czy na pewno chcesz TRWALE usunąć (odpiąć) tę kartę? Tej operacji nie można cofnąć!')) return;
    this.cardService.deleteCard(cardId).subscribe({
      next: () => {
        this.notifSvc.add('Karta została trwale usunięta', 'out');
        this.loadCards();
      },
      error: (err) => this.notifSvc.add(err.error?.error || 'Błąd usuwania karty', 'out')
    });
  }

  onActivateCard(card: any) {
    this.cardService.activateCard(card.id).subscribe({
      next: () => {
        this.notifSvc.add('Karta fizyczna została aktywowana!', 'in');
        this.loadCards();
        this.openDetails(card); // refresh details
      },
      error: (err) => this.notifSvc.add(err.error?.error || 'Błąd aktywacji', 'out')
    });
  }

  onTopUpCard(card: any) {
    const amountStr = prompt('Podaj kwotę doładowania karty Prepaid:');
    if (!amountStr) return;
    const amount = parseFloat(amountStr);
    if (isNaN(amount) || amount <= 0) {
      this.notifSvc.add('Nieprawidłowa kwota', 'out');
      return;
    }
    this.cardService.topUpCard(card.id, amount).subscribe({
      next: (res) => {
        this.notifSvc.add(`Karta doładowana. Nowe saldo: ${res.new_balance} PLN`, 'in');
        this.loadCards();
        this.openDetails(card);
        this.loadAccounts();
      },
      error: (err) => this.notifSvc.add(err.error?.error || 'Błąd doładowania', 'out')
    });
  }

  onSimulateShipping(card: any) {
    this.cardService.simulateShipping(card.id).subscribe({
      next: () => {
        this.notifSvc.add('Zasymulowano wysyłkę. Karta ma status SHIPPED.', 'in');
        this.loadCards();
        this.openDetails(card);
      },
      error: (err) => this.notifSvc.add(err.error?.error || 'Błąd symulacji', 'out')
    });
  }

  // --- Reszta logiki (niezmieniona) ---
  loadBlikTransactions() {
    this.loadingBlik.set(true);
    this.http.get<BlikTransaction[]>('/api/blik/transactions/').pipe(catchError(() => of([]))).subscribe({
      next: (txs) => {
        this.blikTransactions.set(txs);
        this.loadingBlik.set(false);
      },
      error: () => this.loadingBlik.set(false),
    });
  }

  private loadAccounts() {
    this.loadingAccounts.set(true);
    this.http.get<Account[]>('/api/accounts/').subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        this.loadingAccounts.set(false);

        const newBalance = accounts.reduce((s, a) => s + parseFloat(a.balance), 0);
        if (this.previousBalance >= 0 && newBalance > this.previousBalance) {
          const diff = (newBalance - this.previousBalance).toFixed(2);
          this.notifSvc.add(`Otrzymano środki: +${diff} PLN`, 'in');
        }
        this.previousBalance = newBalance;

        if (accounts.length > 0) {
          this.transferForm.patchValue({ sender_account: accounts[0].id });
        }
      },
      error: () => this.loadingAccounts.set(false),
    });
  }

  private loadTransfers() {
    this.loadingTransfers.set(true);
    forkJoin({
      outgoing: this.http.get<Transfer[]>('/api/transfers/').pipe(catchError(() => of([]))),
      incoming: this.http.get<Transfer[]>('/api/transfers/incoming/').pipe(catchError(() => of([]))),
    }).subscribe({
      next: ({ outgoing, incoming }) => {
        const merged = [
          ...outgoing.map(t => ({ ...t, direction: 'OUT' as const })),
          ...incoming.map(t => ({ ...t, direction: 'IN' as const })),
        ].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        this.transfers.set(merged);
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

  closeTransferModal() { 
    this.showTransferModal.set(false); 
  }

  openBlikModal() {
    this.showBlikModal.set(true);
    this.blikCode.set(null);
    this.blikError.set('');
    this.blikConfirmed.set(false);
  }

  closeBlikModal() {
    this.showBlikModal.set(false);
    if (this.blikInterval) clearInterval(this.blikInterval);
    this.blikCode.set(null);
    this.blikConfirmed.set(false);
    this.blikError.set('');
    this.loadBlikTransactions();
    this.loadAccounts();
  }

  generateBlik() {
    const account = this.accounts()[0];
    if (!account) return;

    this.blikLoading.set(true);
    this.blikError.set('');
    this.blikConfirmed.set(false);
    this.blikCode.set(null);

    this.http.post<{ code: string; expires_in: number }>('/api/blik/generate/', { account_id: account.id }).subscribe({
      next: (res) => {
        this.blikCode.set(res.code);
        this.blikTimeLeft.set(res.expires_in ?? 120);
        this.blikLoading.set(false);
        this.blikConfirmed.set(true);
        setTimeout(() => this.blikConfirmed.set(false), 3000);

        if (this.blikInterval) clearInterval(this.blikInterval);
        this.blikInterval = setInterval(() => {
          this.blikTimeLeft.update(t => t - 1);
          if (this.blikTimeLeft() <= 0) {
            clearInterval(this.blikInterval);
            this.blikCode.set(null);
          }
        }, 1000);
      },
      error: (err) => {
        this.blikLoading.set(false);
        this.blikError.set(err?.error?.detail ?? 'Błąd generowania kodu BLIK.');
      },
    });
  }

  submitTransfer() {
    if (this.transferForm.invalid) return;
    this.transferLoading.set(true);
    this.transferError.set('');

    const systemMap = { internal: 'INTERNAL', standard: 'ELIXIR', express: 'EXPRESS_ELIXIR', sorbnet: 'SORBNET' };
    const v = this.transferForm.value;
    const isInternal = this.selectedTransferType() === 'internal';

    const amount = parseFloat((v['amount'] as string) || '0').toFixed(2);
    const recipient = (v['recipient'] as string) || 'odbiorca';

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
        this.notifSvc.add(`Przelew ${amount} PLN → ${recipient} wysłany pomyślnie`, 'out');
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