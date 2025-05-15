def ensure_valid_markdown(text: str) -> str:
    stack = []  
    result = []  
    i = 0  

    
    single_char_symbols = {'*', '`', '~'}
    
    multi_char_symbols = {'```'} 

    while i < len(text):

        processed_multichar = False
        if i + 3 <= len(text): 
            current_segment = text[i:i+3]
            if current_segment in multi_char_symbols:
                tag_to_process = current_segment
                if stack and stack[-1] == tag_to_process:  # Close an open code block
                    stack.pop()
                    result.append(tag_to_process)
                else:  # Open a new code block
                    stack.append(tag_to_process)
                    result.append(tag_to_process)
                i += 3
                processed_multichar = True

        if processed_multichar:
            continue

        
        if text[i] in single_char_symbols:
            tag_to_process = text[i]
            if stack and stack[-1] == tag_to_process:  # Close the tag
                stack.pop()
                result.append(tag_to_process)
            else:  # Open a new tag
                stack.append(tag_to_process)
                result.append(tag_to_process)
            i += 1
        else:
            # Append normal characters
            result.append(text[i])
            i += 1

    
    while stack:
        unmatched = stack.pop()
        
        result.append(unmatched) 

    return ''.join(result)
