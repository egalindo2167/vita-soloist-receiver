#include "../src/search_keyboard.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
int main(void) {
    SearchKeyboard k;search_keyboard_open(&k,"");
    assert(k.open && !k.text[0]);
    UiRect a=search_keyboard_bounds(1,0);
    assert(search_keyboard_input(&k,0,1,a.x,a.y)==KEYBOARD_EDIT && !strcmp(k.text,"a"));
    search_keyboard_input(&k,0,0,a.x,a.y);assert(!strcmp(k.text,"a"));
    UiRect n=search_keyboard_bounds(3,9);
    search_keyboard_input(&k,0,1,n.x+n.w-1,n.y+n.h-1);assert(!strcmp(k.text,"a9"));
    search_keyboard_input(&k,KEY_SPACE,0,0,0);assert(!strcmp(k.text,"a9 "));
    search_keyboard_input(&k,KEY_DELETE,0,0,0);assert(!strcmp(k.text,"a9"));
    k.row=0;k.column=9;search_keyboard_input(&k,KEY_DOWN,0,0,0);assert(k.row==1 && k.column==8);
    search_keyboard_input(&k,KEY_UP,0,0,0);assert(k.row==0 && k.column==8);
    for(unsigned i=0;i<150;++i)search_keyboard_input(&k,KEY_SPACE,0,0,0);
    assert(strlen(k.text)==127 && k.text[127]==0);
    assert(search_keyboard_input(&k,KEY_SEARCH,0,0,0)==KEYBOARD_SUBMIT && !k.open);
    search_keyboard_open(&k,"Canción");search_keyboard_input(&k,KEY_DELETE,0,0,0);assert(!strcmp(k.text,"Canció"));
    search_keyboard_input(&k,KEY_DELETE,0,0,0);assert(!strcmp(k.text,"Canci"));
    assert(search_keyboard_input(&k,KEY_CANCEL,0,0,0)==KEYBOARD_CANCEL && !k.open);
    search_keyboard_open(&k,"");
    UiRect submit=search_keyboard_bounds(4,3);
    assert(search_keyboard_input(&k,0,1,submit.x+submit.w-1,submit.y+submit.h-1)==KEYBOARD_SUBMIT);
    puts("Search keyboard: full touch bounds, held-input suppression, controller editing, UTF-8 deletion and bounded text passed.");
    return 0;
}
