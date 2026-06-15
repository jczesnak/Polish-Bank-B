import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { DecimalPipe, NgIf, NgFor } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { P2pService, PhoneAlias, LookupResult, P2pContact } from '../../core/services/p2p.service';

interface Account {
  id: string;
  iban: string;
  balance: string;
  available_balance: string;
  currency: string;
  account_type_display: string;
}

@Component({
  selector: 'app-p2p',
  standalone: true,
  imports: [ReactiveFormsModule, NgIf, NgFor, DecimalPipe],
  templateUrl: './p2p.component.html',
})
export class P2pComponent implements OnInit {
  private http = inject(HttpClient);
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private notif = inject(NotificationService);
  private p2p = inject(P2pService);

  user = this.auth.user;
  accounts = signal<Account[]>([]);
  aliases = signal<PhoneAlias[]>([]);
  contacts = signal<P2pContact[]>([]);

  transferLoading = signal(false);
  transferError = signal('');
  transferSuccess = signal('');

  lookupResult = signal<LookupResult | null>(null);
  lookupLoading = signal(false);

  aliasLoading = signal(false);
  aliasError = signal('');

  transferForm = this.fb.group({
    sender_account: ['', Validators.required],
    recipient_phone: ['', [Validators.required, Validators.minLength(9)]],
    recipient_name: [''],
    save_contact: [false],
    amount: ['', [Validators.required, Validators.min(0.01)]],
    title: ['Przelew na telefon', Validators.required],
  });

  aliasForm = this.fb.group({
    account_id: ['', Validators.required],
    phone: [''],
  });

  ngOnInit() {
    this.loadAccounts();
    this.loadAliases();
    this.loadContacts();
  }

  private loadContacts() {
    this.p2p.listContacts().subscribe((contacts) => this.contacts.set(contacts));
  }


  selectContact(contact: P2pContact) {
    this.transferForm.patchValue({
      recipient_phone: contact.phone,
      recipient_name: contact.name,
    });
    this.lookupResult.set(null);
  }

  deleteContact(contact: P2pContact, event: Event) {
    event.stopPropagation();
    this.p2p.deleteContact(contact.id).subscribe({
      next: () => this.loadContacts(),
    });
  }

  private loadAccounts() {
    this.http.get<Account[]>('/api/accounts/').subscribe((accounts) => {
      this.accounts.set(accounts);
      if (accounts.length > 0) {
        this.transferForm.patchValue({ sender_account: accounts[0].id });
        this.aliasForm.patchValue({ account_id: accounts[0].id });
      }
    });
  }

  private loadAliases() {
    this.p2p.listAliases().subscribe((aliases) => this.aliases.set(aliases));
  }


  checkNumber() {
    const phone = this.transferForm.value.recipient_phone || '';
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


  submitTransfer() {
    if (this.transferForm.invalid) {
      this.transferForm.markAllAsTouched();
      return;
    }
    this.transferLoading.set(true);
    this.transferError.set('');
    this.transferSuccess.set('');

    const v = this.transferForm.value;
    const amount = parseFloat((v.amount as string) || '0').toFixed(2);

    this.p2p
      .transfer({
        sender_account: v.sender_account as string,
        recipient_phone: v.recipient_phone as string,
        recipient_name: (v.recipient_name as string) || undefined,
        save_contact: !!v.save_contact,
        amount: amount,
        title: v.title as string,
      })
      .subscribe({
        next: (res) => {
          this.transferLoading.set(false);
          const who = res.recipient_name || res.recipient_phone;
          this.transferSuccess.set(
            `Wysłano ${res.amount} PLN do ${who} (bank: ${res.recipient_bank}).`,
          );
          this.notif.add(`Przelew na telefon ${res.amount} PLN → ${who}`, 'out');
          if (res.contact_saved) this.loadContacts();
          this.transferForm.patchValue({ recipient_phone: '', recipient_name: '', amount: '', save_contact: false });
          this.lookupResult.set(null);
          this.loadAccounts();
        },
        error: (err) => {
          this.transferLoading.set(false);
          this.transferError.set(this.extractError(err, 'Błąd przelewu na telefon.'));
        },
      });
  }


  registerAlias() {
    if (this.aliasForm.invalid) {
      this.aliasForm.markAllAsTouched();
      return;
    }
    this.aliasLoading.set(true);
    this.aliasError.set('');

    const v = this.aliasForm.value;
    this.p2p
      .registerAlias({
        account_id: v.account_id as string,
        phone: (v.phone as string) || undefined,
      })
      .subscribe({
        next: () => {
          this.aliasLoading.set(false);
          this.aliasForm.patchValue({ phone: '' });
          this.loadAliases();
        },
        error: (err) => {
          this.aliasLoading.set(false);
          this.aliasError.set(this.extractError(err, 'Nie udało się zarejestrować aliasu.'));
        },
      });
  }

  deleteAlias(alias: PhoneAlias) {
    this.p2p.deleteAlias(alias.phone).subscribe({
      next: () => this.loadAliases(),
      error: (err) => this.aliasError.set(this.extractError(err, 'Nie udało się usunąć aliasu.')),
    });
  }

  private extractError(err: any, fallback: string): string {
    const data = err?.error;
    if (data?.detail) return data.detail;
    if (typeof data === 'object' && data) return Object.values(data).flat().join(' ');
    return fallback;
  }
}
