#ifndef RECEIVER_SEARCH_KEYBOARD_H
#define RECEIVER_SEARCH_KEYBOARD_H
#include "ui_layout.h"
enum { KEY_UP=1,KEY_DOWN=2,KEY_LEFT=4,KEY_RIGHT=8,KEY_ENTER=16,KEY_CANCEL=32,
       KEY_DELETE=64,KEY_SEARCH=128,KEY_SPACE=256,KEY_CLEAR=512 };
enum { KEYBOARD_EDIT,KEYBOARD_SUBMIT,KEYBOARD_CANCEL };
typedef struct { char text[128];unsigned open,row,column; } SearchKeyboard;
void search_keyboard_open(SearchKeyboard *keyboard,const char *initial);
unsigned search_keyboard_input(SearchKeyboard *keyboard,unsigned keys,int fresh,int x,int y);
unsigned search_keyboard_columns(unsigned row);
const char *search_keyboard_label(unsigned row,unsigned column);
char search_keyboard_character(unsigned row,unsigned column);
UiRect search_keyboard_bounds(unsigned row,unsigned column);
#endif
