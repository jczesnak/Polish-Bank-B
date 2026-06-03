import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';

@Injectable({ providedIn: 'root' })
export class CardService {
  private http = inject(HttpClient);

  getCards() {
    return this.http.get<any[]>('/api/cards/my-cards/');
  }

  orderCard() {
    return this.http.post<any>('/api/cards/order/', {});
  }

  blockCard(cardId: number) {
    return this.http.post<any>(`/api/cards/${cardId}/block/`, {});
  }

   getCardDetails(cardId: number) {
  return this.http.get<any>(`/api/cards/${cardId}/details/`);
}
}