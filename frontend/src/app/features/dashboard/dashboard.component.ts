import { Component, OnInit, signal, inject, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { RouterLink } from '@angular/router';
import { FormBuilder, ReactiveFormsModule, Validators, FormsModule } from '@angular/forms';
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

export interface CardTransaction {
  id: number;
  amount: string;
  currency: string;
  merchant_name: string;
  status: string;
  created_at: string;
}

export interface UnifiedTransaction {
  id: string;
  type: 'TRANSFER' | 'BLIK' | 'CARD';
  amount: string;
  currency: string;
  status: string;
  created_at: string;
  direction: 'IN' | 'OUT';
  title: string;
  

  sender_name?: string;
  sender_iban?: string;
  recipient_name?: string;
  recipient_iban?: string;
  system_route?: string;
  system_route_display?: string;
  merchant_name?: string;
  aml_explanation?: string;
}

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
  aml_explanation?: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [NgClass, NgIf, NgFor, RouterLink, ReactiveFormsModule, FormsModule, DecimalPipe, DatePipe, SlicePipe],
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
  allTransactions = signal<UnifiedTransaction[]>([]);
  blikTransactions = signal<BlikTransaction[]>([]);
  

  cards = signal<any[]>([]);
  loadingCards = signal(false);
  currentCardIndex = signal(0);
  
  juniors = signal<any[]>([]);
  loadingJuniors = signal(false);
  showJuniorModal = signal(false);
  selectedJunior = signal<any>(null);

  juniorTransferRequests = signal<any[]>([]);
  showTransferApprovalModal = signal(false);
  selectedTransferRequest = signal<any>(null);
  transferApprovalLoading = signal(false);
  transferApprovalError = signal('');
  
  juniorLimitsForm = this.fb.group({
    daily_limit: ['', Validators.required],
    blik_limit: ['', Validators.required],
  });

  showCreateJuniorModal = signal(false);
  createJuniorLoading = signal(false);
  createJuniorError = signal('');
  createJuniorForm = this.fb.group({
    first_name: ['', Validators.required],
    last_name: ['', Validators.required],
    pesel: ['', [Validators.required, Validators.pattern('^[0-9]{11}$')]],
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(8)]],
    daily_limit: [100.00],
    blik_limit: [50.00]
  });

  showTopUpModal = signal(false);
  selectedJuniorForTopUp = signal<any>(null);
  topUpMode = signal<'account' | 'card'>('account');
  topUpLoading = signal(false);
  topUpError = signal('');
  topUpSuccess = signal('');
  topUpForm = this.fb.group({
    amount: ['', [Validators.required, Validators.min(0.01)]],
  });

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
  hoveredChartPoint = signal<any>(null);

  loadingAccounts = signal(true);
  loadingTransfers = signal(true);
  loadingBlik = signal(true);
  private previousBalance = -1;


  showTransferModal = signal(false);
  showBlikModal = signal(false);

  selectedTransferType = signal<'internal' | 'standard' | 'express' | 'sorbnet' | 'swift'>('internal');
  transferLoading = signal(false);
  transferError = signal('');

  blikCode = signal<string | null>(null);
  blikTimeLeft = signal<number>(0);
  blikInterval: any;
  blikLoading = signal(false);
  blikError = signal('');

  // AML Modal State
  isAmlModalOpen = signal(false);
  selectedAmlTransfer = signal<UnifiedTransaction | Transfer | null>(null);
  amlExplanation = signal('');
  amlLoading = signal(false);
  amlError = signal('');

  blikConfirmed = signal(false);

  pendingBlikTransaction = signal<BlikTransaction | null>(null);
  blikAuthForm = this.fb.group({ pin: ['', [Validators.required, Validators.pattern('^[0-9]{4}$')]] });
  blikAuthLoading = signal(false);
  blikAuthError = signal('');

  historyFilter = signal<'all' | 'out' | 'in' | 'card' | 'blik' | 'transfer'>('all');

  readonly historyFilters = [
    { key: 'all' as const, label: 'Wszystkie' },
    { key: 'out' as const, label: 'Wychodzące' },
    { key: 'in' as const, label: 'Przychodzące' },
    { key: 'card' as const, label: 'Karty' },
    { key: 'blik' as const, label: 'BLIK / P2P' },
    { key: 'transfer' as const, label: 'Przelewy' },
  ];

  readonly filteredTransfers = computed(() => {
    const f = this.historyFilter();
    const all = this.allTransactions();
    if (f === 'all') return all;
    if (f === 'out') return all.filter(t => t.direction === 'OUT');
    if (f === 'in') return all.filter(t => t.direction === 'IN');
    if (f === 'card') return all.filter(t => t.type === 'CARD');
    if (f === 'blik') return all.filter(t => t.type === 'BLIK' || (t.type === 'TRANSFER' && (t.system_route_display === 'KLIK' || (t as any).system_route === 'KLIK')));
    if (f === 'transfer') return all.filter(t => t.type === 'TRANSFER' && t.system_route_display !== 'KLIK' && (t as any).system_route !== 'KLIK');
    return all;
  });

  readonly historyCounts = computed(() => {
    const all = this.allTransactions();
    return {
      all: all.length,
      out: all.filter(t => t.direction === 'OUT').length,
      in: all.filter(t => t.direction === 'IN').length,
      card: all.filter(t => t.type === 'CARD').length,
      blik: all.filter(t => t.type === 'BLIK' || (t.type === 'TRANSFER' && (t.system_route_display === 'KLIK' || (t as any).system_route === 'KLIK'))).length,
      transfer: all.filter(t => t.type === 'TRANSFER' && t.system_route_display !== 'KLIK' && (t as any).system_route !== 'KLIK').length,
    };
  });

  readonly transferTypes = [
    { key: 'internal' as const, label: 'Wewnętrzny' },
    { key: 'standard' as const, label: 'Elixir' },
    { key: 'express' as const, label: 'Express' },
    { key: 'sorbnet' as const, label: 'Sorbnet' },
    { key: 'swift' as const, label: 'SWIFT' },
  ];

  readonly selectedTypeInfo = computed(() => {
    const map = {
      internal: { time: 'Zaksięgujemy natychmiast', fee: 'Darmowy' },
      standard: { time: 'Rozliczenie w sesjach KIR', fee: 'Darmowy' },
      express:  { time: 'Przelew natychmiastowy', fee: 'Darmowy' },
      sorbnet:  { time: 'System RTGS dla dużych kwot', fee: 'Prowizja 1 PLN' },
      swift:    { time: 'Przelew zagraniczny (1-2 dni)', fee: 'Prowizja 0,35%' },
    };
    return map[this.selectedTransferType() as keyof typeof map] || { time: '', fee: '' };
  });

  readonly totalBalance = computed(() =>
    this.accounts().reduce((sum, acc) => sum + parseFloat(acc.balance), 0),
  );

  readonly wydatki = computed(() =>
    this.allTransactions().filter(t => t.direction === 'OUT')
      .reduce((sum, t) => sum + parseFloat(t.amount), 0)
  );

  readonly wplywy = computed(() =>
    this.allTransactions().filter(t => t.direction === 'IN')
      .reduce((sum, t) => sum + parseFloat(t.amount), 0)
  );

  readonly balanceChart = computed(() => {
    const sorted = [...this.allTransactions()]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    const current = this.totalBalance();
    const rawPoints: { label: string; balance: number; transaction?: any }[] = [
      { label: 'Teraz', balance: current },
    ];

    let running = current;
    for (const t of sorted.slice(0, 14)) { // Pobieramy do 14 punktów dla lepszego wykresu
      running += t.direction === 'OUT' ? parseFloat(t.amount) : -parseFloat(t.amount);
      const d = new Date(t.created_at);
      rawPoints.push({
        label: d.toLocaleDateString('pl-PL', { day: 'numeric', month: 'short' }),
        balance: Math.max(0, running),
        transaction: t
      });
    }

    const reversed = rawPoints.reverse();
    if (reversed.length < 2) return null;

    const minBal = Math.min(...reversed.map(p => p.balance));
    const maxBal = Math.max(...reversed.map(p => p.balance), 1);
    const range = maxBal - minBal || 1;


    const w = 1000;
    const h = 300;
    

    const points = reversed.map((p, i) => {
      const x = (i / (reversed.length - 1)) * w;
      const normalized = (p.balance - minBal) / range;
      const y = h - (h * 0.1) - (normalized * h * 0.8);
      

      const tooltipX = x < w * 0.2 ? '0%' : (x > w * 0.8 ? '-100%' : '-50%');
      const tooltipY = y < h * 0.35 ? '15px' : '-115%';
      
      return {
        ...p,
        balanceStr: p.balance.toLocaleString('pl-PL', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
        x, y,
        isCurrent: p.label === 'Teraz',
        tooltipTransform: `translate(${tooltipX}, ${tooltipY})`
      };
    });


    let pathD = `M ${points[0].x},${points[0].y}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p1 = points[i];
      const p2 = points[i+1];
      const ctrlX1 = p1.x + (p2.x - p1.x) / 3;
      const ctrlX2 = p2.x - (p2.x - p1.x) / 3;
      pathD += ` C ${ctrlX1},${p1.y} ${ctrlX2},${p2.y} ${p2.x},${p2.y}`;
    }

    const areaD = `${pathD} L ${w},${h} L 0,${h} Z`;

    return { points, pathD, areaD, minBal, maxBal };
  });

  transferForm = this.fb.group({
    sender_account: [''],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    recipient: [''],
    account_number: ['', Validators.required],
    title: ['', Validators.required],
    swift_charge_bearer: ['SHA'],
  });

  orderCardForm = this.fb.group({
    card_type: ['VIRTUAL', Validators.required],
    initial_balance: [0, [Validators.min(0)]],
  });

  pollingInterval: any;

  ngOnInit() {
    this.loadAccounts();
    this.loadTransfers();
    this.loadBlikTransactions();
    this.loadCards();
    this.loadJuniors();

    this.loadJuniorTransferRequests();

    // Start polling for new transactions and balance changes
    this.pollingInterval = setInterval(() => {
      this.loadAccounts(true);
      this.loadTransfers(true);
      this.loadCards();
      this.loadJuniors(true);
      this.loadJuniorTransferRequests();
    }, 3000);
  }

  loadJuniors(silent = false) {
    if (!silent) this.loadingJuniors.set(true);
    this.http.get<any[]>('/api/accounts/junior/').subscribe({
      next: (data) => {
        this.juniors.set(data);
        if (!silent) this.loadingJuniors.set(false);
      },
      error: () => {
        if (!silent) this.loadingJuniors.set(false);
      }
    });
  }

  loadJuniorTransferRequests() {
    this.http.get<any[]>('/api/accounts/parent/transfer-requests/').subscribe({
      next: (data) => {
        const prev = this.juniorTransferRequests();
        if (data.length > prev.length) {
          this.notifSvc.add(`Nowy wniosek przelewowy od ${data[0]?.junior_name}`, 'out');
        }
        this.juniorTransferRequests.set(data);
      },
      error: () => {},
    });
  }

  openTransferApproval(req: any) {
    this.selectedTransferRequest.set(req);
    this.transferApprovalError.set('');
    this.showTransferApprovalModal.set(true);
  }

  approveTransferRequest() {
    const req = this.selectedTransferRequest();
    if (!req) return;
    this.transferApprovalLoading.set(true);
    this.transferApprovalError.set('');
    this.http.post(`/api/accounts/parent/transfer-requests/${req.id}/approve/`, {}).subscribe({
      next: () => {
        this.transferApprovalLoading.set(false);
        this.showTransferApprovalModal.set(false);
        this.selectedTransferRequest.set(null);
        this.notifSvc.add('Przelew zatwierdzony i wykonany!', 'in');
        this.loadAccounts();
        this.loadTransfers();
        this.loadJuniorTransferRequests();
      },
      error: (err) => {
        this.transferApprovalLoading.set(false);
        this.transferApprovalError.set(err?.error?.detail || 'Błąd zatwierdzania.');
      },
    });
  }

  rejectTransferRequest() {
    const req = this.selectedTransferRequest();
    if (!req) return;
    this.transferApprovalLoading.set(true);
    this.http.post(`/api/accounts/parent/transfer-requests/${req.id}/reject/`, {}).subscribe({
      next: () => {
        this.transferApprovalLoading.set(false);
        this.showTransferApprovalModal.set(false);
        this.selectedTransferRequest.set(null);
        this.notifSvc.add('Wniosek przelewowy odrzucony.', 'out');
        this.loadJuniorTransferRequests();
      },
      error: () => {
        this.transferApprovalLoading.set(false);
      },
    });
  }

  openJuniorModal(junior: any) {
    this.selectedJunior.set(junior);
    this.juniorLimitsForm.patchValue({
      daily_limit: junior.daily_limit,
      blik_limit: junior.blik_limit
    });
    this.showJuniorModal.set(true);
  }
  
  closeJuniorModal() {
    this.showJuniorModal.set(false);
    this.selectedJunior.set(null);
  }
  
  saveJuniorLimits() {
    if (this.juniorLimitsForm.invalid || !this.selectedJunior()) return;
    this.http.patch(`/api/accounts/junior/${this.selectedJunior().id}/`, this.juniorLimitsForm.value).subscribe({
      next: () => {
        this.notifSvc.add('Limity zapisane', 'in');
        this.closeJuniorModal();
        this.loadJuniors();
      },
      error: () => this.notifSvc.add('Błąd zapisu', 'out')
    });
  }

  openCreateJuniorModal() {
    this.showCreateJuniorModal.set(true);
    this.createJuniorForm.reset({ daily_limit: 100, blik_limit: 50 });
    this.createJuniorError.set('');
  }

  closeCreateJuniorModal() {
    this.showCreateJuniorModal.set(false);
  }

  submitCreateJunior() {
    if (this.createJuniorForm.invalid) return;
    this.createJuniorLoading.set(true);
    this.createJuniorError.set('');

    this.http.post('/api/accounts/junior/', this.createJuniorForm.value).subscribe({
      next: () => {
        this.notifSvc.add('Konto Junior zostało pomyślnie utworzone!', 'in');
        this.createJuniorLoading.set(false);
        this.closeCreateJuniorModal();
        this.loadJuniors();
      },
      error: (err) => {
        this.createJuniorLoading.set(false);
        const data = err?.error;
        if (typeof data === 'object') {
          this.createJuniorError.set(Object.values(data).flat().join(' '));
        } else {
          this.createJuniorError.set('Wystąpił błąd podczas tworzenia konta.');
        }
      }
    });
  }

  openTopUpModal(junior: any) {
    this.selectedJuniorForTopUp.set(junior);
    this.topUpMode.set('account');
    this.topUpForm.reset();
    this.topUpError.set('');
    this.topUpSuccess.set('');
    this.showTopUpModal.set(true);
  }

  closeTopUpModal() {
    this.showTopUpModal.set(false);
    this.selectedJuniorForTopUp.set(null);
  }

  submitTopUp() {
    if (this.topUpForm.invalid || !this.selectedJuniorForTopUp()) return;
    this.topUpLoading.set(true);
    this.topUpError.set('');
    this.topUpSuccess.set('');

    const url = this.topUpMode() === 'card'
      ? `/api/accounts/junior/${this.selectedJuniorForTopUp().id}/topup-card/`
      : `/api/accounts/junior/${this.selectedJuniorForTopUp().id}/topup/`;

    this.http.post<any>(url, this.topUpForm.value).subscribe({
      next: (res) => {
        this.topUpLoading.set(false);
        this.topUpSuccess.set(res.detail || 'Sukces!');
        this.notifSvc.add(res.detail || 'Doładowanie Junior', 'in');
        this.loadJuniors();
        this.loadAccounts();
        setTimeout(() => this.closeTopUpModal(), 1800);
      },
      error: (err) => {
        this.topUpLoading.set(false);
        const data = err?.error;
        if (typeof data === 'object') {
          this.topUpError.set(Object.values(data).flat().join(' '));
        } else {
          this.topUpError.set('Wystąpił błąd.');
        }
      }
    });
  }

  ngOnDestroy() {
    if (this.pollingInterval) clearInterval(this.pollingInterval);
    if (this.blikInterval) clearInterval(this.blikInterval);
  }

  authorizeBlikTransaction() {
    if (this.blikAuthForm.invalid || !this.pendingBlikTransaction()) return;
    this.blikAuthLoading.set(true);
    this.blikAuthError.set('');

    this.http.post(`/api/blik/transactions/${this.pendingBlikTransaction()?.id}/authorize/`, this.blikAuthForm.value).subscribe({
      next: () => {
        this.blikAuthLoading.set(false);
        this.pendingBlikTransaction.set(null);
        this.notifSvc.add('Transakcja BLIK autoryzowana pomyślnie!', 'in');
        this.loadAccounts();
        this.loadTransfers();
      },
      error: (err) => {
        this.blikAuthLoading.set(false);
        this.blikAuthError.set(err.error?.pin || err.error?.detail || 'Błąd autoryzacji.');
      }
    });
  }

  rejectBlikTransaction() {
    if (!this.pendingBlikTransaction()) return;
    this.blikAuthLoading.set(true);
    this.blikAuthError.set('');

    this.http.post(`/api/blik/transactions/${this.pendingBlikTransaction()?.id}/reject/`, {}).subscribe({
      next: () => {
        this.blikAuthLoading.set(false);
        this.pendingBlikTransaction.set(null);
        this.notifSvc.add('Transakcja BLIK została odrzucona.', 'out');
        this.loadAccounts();
        this.loadTransfers();
      },
      error: (err) => {
        this.blikAuthLoading.set(false);
        this.blikAuthError.set('Błąd odrzucania transakcji.');
      }
    });
  }

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


  loadBlikTransactions(silent = false) {
    if (!silent) this.loadingBlik.set(true);
    this.http.get<BlikTransaction[]>('/api/blik/transactions/').pipe(catchError(() => of([]))).subscribe({
      next: (txs) => {
        this.blikTransactions.set(txs);
        if (!silent) this.loadingBlik.set(false);

        // Check for pending transactions
        const pending = txs.find(t => t.status === 'PENDING');
        if (pending && !this.pendingBlikTransaction()) {
          this.pendingBlikTransaction.set(pending);
          this.blikAuthForm.reset();
        } else if (!pending && this.pendingBlikTransaction()) {
          // It was authorized/rejected elsewhere or timed out
          this.pendingBlikTransaction.set(null);
        }
      },
      error: () => {
        if (!silent) this.loadingBlik.set(false);
      },
    });
  }

  private loadAccounts(silent = false) {
    if (!silent) this.loadingAccounts.set(true);
    this.http.get<Account[]>('/api/accounts/').subscribe({
      next: (accounts) => {
        this.accounts.set(accounts);
        if (!silent) this.loadingAccounts.set(false);

        const newBalance = accounts.reduce((s, a) => s + parseFloat(a.balance), 0);
        if (this.previousBalance >= 0 && newBalance > this.previousBalance) {
          const diff = (newBalance - this.previousBalance).toFixed(2);
          this.notifSvc.add(`Otrzymano środki: +${diff} PLN`, 'in');
        }
        this.previousBalance = newBalance;

        if (accounts.length > 0 && !this.transferForm.get('sender_account')?.value) {
          this.transferForm.patchValue({ sender_account: accounts[0].id });
        }
      },
      error: () => {
        if (!silent) this.loadingAccounts.set(false);
      },
    });
  }

  private loadTransfers(silent = false) {
    if (!silent) this.loadingTransfers.set(true);
    forkJoin({
      outgoing: this.http.get<Transfer[]>('/api/transfers/').pipe(catchError(() => of([]))),
      incoming: this.http.get<Transfer[]>('/api/transfers/incoming/').pipe(catchError(() => of([]))),
      blik: this.http.get<BlikTransaction[]>('/api/blik/transactions/').pipe(catchError(() => of([]))),
      cards: this.http.get<CardTransaction[]>('/api/cards/transactions/').pipe(catchError(() => of([])))
    }).subscribe({
      next: ({ outgoing, incoming, blik, cards }) => {
        const unified: UnifiedTransaction[] = [];
        
        outgoing.forEach(t => unified.push({
          id: t.id, type: 'TRANSFER', direction: 'OUT',
          amount: t.amount, currency: 'PLN', status: t.status, created_at: t.created_at,
          title: t.title, recipient_name: t.recipient_name, system_route_display: t.system_route_display || t.system_route,
          system_route: t.system_route, aml_explanation: t.aml_explanation
        }));
        
        incoming.forEach(t => unified.push({
          id: t.id, type: 'TRANSFER', direction: 'IN',
          amount: t.amount, currency: 'PLN', status: t.status, created_at: t.created_at,
          title: t.title, sender_name: t.sender_name || t.sender_iban, system_route_display: t.system_route_display || t.system_route,
          system_route: t.system_route
        }));
        
        blik.forEach(t => unified.push({
          id: String(t.id), type: 'BLIK', direction: 'OUT',
          amount: t.amount, currency: t.currency, status: t.status, created_at: t.created_at,
          title: 'Płatność BLIK', merchant_name: t.merchant_name, system_route: 'KLIK'
        }));
        
        cards.forEach(t => unified.push({
          id: String(t.id), type: 'CARD', direction: 'OUT',
          amount: t.amount, currency: t.currency, status: t.status, created_at: t.created_at,
          title: 'Płatność Kartą', merchant_name: t.merchant_name, system_route: 'CARD'
        }));

        const merged = unified.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
        this.allTransactions.set(merged);
        if (!silent) this.loadingTransfers.set(false);
      },
      error: () => {
        if (!silent) this.loadingTransfers.set(false);
      },
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

  copyBlikCode() {
    const code = this.blikCode();
    if (code) {
      navigator.clipboard.writeText(code).then(() => {
        this.notifSvc.add('Skopiowano kod BLIK do schowka', 'in');
      }).catch(() => {
        this.notifSvc.add('Nie udało się skopiować kodu', 'out');
      });
    }
  }

  submitTransfer() {
    if (this.transferForm.invalid) return;
    this.transferLoading.set(true);
    this.transferError.set('');

    const systemMap: Record<string, string> = { internal: 'INTERNAL', standard: 'ELIXIR', express: 'EXPRESS_ELIXIR', sorbnet: 'SORBNET', swift: 'SWIFT' };
    const v = this.transferForm.value;
    const isInternal = this.selectedTransferType() === 'internal';
    const isSwift = this.selectedTransferType() === 'swift';

    const amount = parseFloat((v['amount'] as string) || '0').toFixed(2);
    const recipient = (v['recipient'] as string) || 'odbiorca';

    const payload: any = {
      sender_account: v['sender_account'],
      recipient_iban: (v['account_number'] as string).replace(/\s/g, ''),
      recipient_name: v['recipient'],
      amount: v['amount'],
      title: v['title'],
      system_route: systemMap[this.selectedTransferType()],
    };
    if (isSwift) {
      payload['swift_charge_bearer'] = (v as any)['swift_charge_bearer'] || 'SHA';
    }

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

  openAmlModal(transfer: UnifiedTransaction | Transfer) {
    this.selectedAmlTransfer.set(transfer);
    this.amlExplanation.set('');
    this.amlError.set('');
    this.isAmlModalOpen.set(true);
  }

  closeAmlModal() {
    this.isAmlModalOpen.set(false);
    this.selectedAmlTransfer.set(null);
  }

  submitAmlExplanation() {
    const transfer = this.selectedAmlTransfer();
    const explanation = this.amlExplanation().trim();
    if (!transfer || !explanation) return;

    this.amlLoading.set(true);
    this.amlError.set('');

    this.http.post<{status: string, message: string}>(`/api/transfers/${transfer.id}/aml-explain/`, { explanation })
      .subscribe({
        next: (res) => {
          this.amlLoading.set(false);
          this.notifSvc.add(res.message, res.status === 'ZAAKCEPTOWANE' ? 'in' : 'out');
          this.closeAmlModal();
          this.loadTransfers(); // Refresh the list
        },
        error: (err) => {
          this.amlLoading.set(false);
          this.amlError.set(err.error?.error || 'Błąd podczas wysyłania wyjaśnienia');
        }
      });
  }
}