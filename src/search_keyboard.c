#include "search_keyboard.h"
#include <string.h>
static const char *letters[]={"qwertyuiop","asdfghjkl","zxcvbnm","0123456789"};
unsigned search_keyboard_columns(unsigned row) { return row<4?(unsigned)strlen(letters[row]):4; }
char search_keyboard_character(unsigned row,unsigned column) {
    return row<4 && column<search_keyboard_columns(row)?letters[row][column]:0;
}
const char *search_keyboard_label(unsigned row,unsigned column) {
    static const char *actions[]={"Space","Delete","Clear","Search"};
    return row==4 && column<4?actions[column]:"";
}
UiRect search_keyboard_bounds(unsigned row,unsigned column) {
    if(row==4)return (UiRect){196+(int)column*184,426,172,60};
    return (UiRect){202+(int)(10-search_keyboard_columns(row))*36+(int)column*72,200+(int)row*54,66,48};
}
void search_keyboard_open(SearchKeyboard *k,const char *initial) {
    memset(k,0,sizeof(*k));k->open=1;
    size_t n=strlen(initial);
    if(n>127) { n=127;while(n && ((unsigned char)initial[n]&0xc0)==0x80)--n; }
    memcpy(k->text,initial,n);
}
static void erase(SearchKeyboard *k) {
    size_t n=strlen(k->text);if(!n)return;
    do { --n; }while(n && ((unsigned char)k->text[n]&0xc0)==0x80);
    k->text[n]=0;
}
static void append(SearchKeyboard *k,char c) {
    size_t n=strlen(k->text);if(n<127) { k->text[n]=c;k->text[n+1]=0; }
}
unsigned search_keyboard_input(SearchKeyboard *k,unsigned keys,int fresh,int x,int y) {
    if(keys&KEY_CANCEL) { k->open=0;return KEYBOARD_CANCEL; }
    if(keys&KEY_SEARCH) { k->open=0;return KEYBOARD_SUBMIT; }
    if(keys&KEY_DELETE)erase(k);
    if(keys&KEY_SPACE)append(k,' ');
    if(keys&KEY_CLEAR)k->text[0]=0;
    if(keys&KEY_UP)k->row=(k->row+4)%5;
    if(keys&KEY_DOWN)k->row=(k->row+1)%5;
    unsigned columns=search_keyboard_columns(k->row);
    if(k->column>=columns)k->column=columns-1;
    if(keys&KEY_LEFT)k->column=(k->column+columns-1)%columns;
    if(keys&KEY_RIGHT)k->column=(k->column+1)%columns;
    int activate=!!(keys&KEY_ENTER);
    if(fresh)for(unsigned row=0;row<5;++row)for(unsigned col=0;col<search_keyboard_columns(row);++col)
        if(ui_hit(search_keyboard_bounds(row,col),x,y)) { k->row=row;k->column=col;activate=1; }
    if(activate) {
        if(k->row<4)append(k,letters[k->row][k->column]);
        else if(k->column==0)append(k,' ');
        else if(k->column==1)erase(k);
        else if(k->column==2)k->text[0]=0;
        else { k->open=0;return KEYBOARD_SUBMIT; }
    }
    return KEYBOARD_EDIT;
}
