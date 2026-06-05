import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class CardService {
  private http = inject(HttpClient);

  getCards() {
    return this.http.get<any[]>('/api/cards/my-cards/');
  }

  orderCard(card_type: string, initial_balance: number) {
    return this.http.post<any>('/api/cards/order/', { card_type, initial_balance });
  }

  blockCard(cardId: number) {
    return this.http.post<any>(`/api/cards/${cardId}/block/`, {});
  }

  unblockCard(cardId: number) {
    return this.http.post<any>(`/api/cards/${cardId}/unblock/`, {});
  }

  getCardDetails(cardId: number) {
    return this.http.get<any>(`/api/cards/${cardId}/details/`);
  }

  deleteCard(cardId: number) {
    return this.http.delete<any>(`/api/cards/${cardId}/delete/`);
  }

  activateCard(cardId: number) {
    return this.http.post<any>(`/api/cards/${cardId}/activate/`, {});
  }

  topUpCard(cardId: number, amount: number) {
    return this.http.post<any>(`/api/cards/${cardId}/topup/`, { amount });
  }

  simulateShipping(cardId: number) {
    return this.http.post<any>(`/api/cards/${cardId}/simulate-shipping/`, {});
  }
}