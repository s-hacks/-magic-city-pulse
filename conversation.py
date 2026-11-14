"""Bounded conversation context and deterministic topic changes."""
import re


def history(value):
    if not isinstance(value,list): return []
    turns=[]
    for turn in value[-10:]:
        if not isinstance(turn,dict): continue
        if turn.get('role') not in ('user','assistant') or not isinstance(turn.get('content'),str): continue
        content=turn['content'].strip()[:700]
        if content: turns.append({'role':turn['role'],'content':content})
    return turns


def category(message):
    patterns=[('food',r'food|pantr(?:y|ies)|hungry|meals?|grocer(?:y|ies)|bags|snap|eat'),
              ('shelter',r'shelter|sheleter|homeless|beds?|place to (?:stay|sleep)|somewhere (?:to )?(?:stay|sleep)|nowhere to (?:stay|sleep|go)|sleep|roof over my head'),
              ('health',r'clinic|health(?:care)?|doctor|medical|medicine|not feeling well')]
    # "I have food, but now need somewhere to stay" must honor the latest need.
    clauses=re.split(r'\b(?:but|now|instead|actually|also|then|next)\b',message.lower())
    for clause in reversed(clauses):
        for name,pattern in patterns:
            if re.search(r'\b(?:'+pattern+r')\b',clause): return name
    return None


def quick_replies(missing=()):
    if 'category' in missing:
        return [{'label':'🥕 Find a meal','message':'I need free food'},
                {'label':'🏡 A place to stay','message':'I need a place to stay'},
                {'label':'🌷 Find a clinic','message':'I need a clinic'}]
    if 'gender' in missing:
        return [{'label':'Female','message':'female'},{'label':'Male','message':'male'},
                {'label':'Family','message':'family'},{'label':'Nonbinary','message':'nonbinary'}]
    if 'date_time' in missing:
        return [{'label':'Tonight','message':'tonight'},{'label':'Tomorrow morning','message':'tomorrow morning'}]
    return []


def followup(message,previous,ids,load):
    if not isinstance(ids,list): return None
    next_category=category(message)
    if next_category and next_category!=previous.get('category'): return None
    lower=message.lower()
    if not re.search(r'what (?:should|do|can|to)|bring|requirements?|how (?:do|can) i get|directions?|bus stop|check.?in|is (?:it|that|the .*one) open|hours|tell me (?:more|about)',lower): return None
    rows={r['id']:r for r in load()}
    matched=[rows[i] for i in ids[:3] if isinstance(i,str) and i in rows and rows[i]['category']==previous.get('category')]
    if not matched: return None
    index=1 if re.search(r'\b(second|2nd)\b',lower) else 2 if re.search(r'\b(third|3rd)\b',lower) else 0
    if index>=len(matched): return {'reply':'I don’t have that option in the current results. Which listed place did you mean?','intent':'conversation','needs_info':False,'state':previous}
    resource=matched[index]
    for r in matched:
        if r['name'].split(' (')[0].lower() in lower: resource=r;break
    if re.search(r'bring|requirements?|what (?:should|do|can|to)',lower):
        detail='What to bring: '+resource['what_to_bring']
    elif re.search(r'directions?|how (?:do|can) i get|bus stop',lower):
        detail='Listed connection: '+resource['nearest_max_stop']+'. Tap “Plan my route” for walking directions, or check current transit directions. Bus fares may apply.'
    else:
        detail='Listed hours: '+resource['hours_today']+f". Current listing status: {resource['status']}. Confirm with the provider before traveling."
    if resource['category']=='shelter': detail+=' Check-in: '+resource.get('check_in_window','Contact provider')+'.'
    if resource.get('is_demo') or resource.get('availability_is_demo'): detail+=' This listing or its availability includes demo data.'
    return {'reply':resource['name']+' — '+detail,'intent':'conversation','needs_info':False,
            'state':previous,'focus_resource_id':resource['id']}


def comparison(message,previous,context,load):
    """Answer a relationship question without starting another category search."""
    lower=message.lower()
    relation=re.search(r'\b(close|closy|nearby|near each|near one|far|apart|distance|between|walk|both|night|tonight)\b',lower)
    question=re.search(r'\b(is|are|how|can|would|since)\b',lower)
    refers_both=(re.search(r'\b(food|meal|pantry)\b',lower) and re.search(r'\b(shelter|place to stay)\b',lower)) or re.search(r'\b(they|them|both|those places|two places)\b',lower)
    if not (relation and question and refers_both): return None
    base={'intent':'comparison','needs_info':False,'state':previous}
    rows={r['id']:r for r in load()}
    context=context if isinstance(context,dict) else {}
    pair=[];used_first=[]
    for category_name in ('food','shelter'):
        info=context.get(category_name,{})
        if not isinstance(info,dict): info={}
        ids=info.get('ids',[]);ids=ids[:3] if isinstance(ids,list) else []
        valid=[rows[i] for i in ids if isinstance(i,str) and i in rows and rows[i]['category']==category_name]
        selected=next((r for r in valid if r['id']==info.get('selected_id')),None)
        if not valid:
            return {**base,'reply':'I can compare them, but I need to know which food place and shelter you mean. Pick a card from each of our earlier results first.'}
        pair.append(selected or valid[0])
        if not selected and len(valid)>1: used_first.append(category_name)
    from scripts.build_dataset import distance
    from scripts.availability import scheduled_status
    from datetime import datetime
    from zoneinfo import ZoneInfo
    food,shelter=pair
    miles=distance(food['lat'],food['lon'],shelter['lat'],shelter['lon'])/1.609344
    reply=f"{food['name']} and {shelter['name']} are about {miles:.1f} miles apart in a straight line. The walking route may be longer. "
    if used_first: reply+='I’m comparing the first '+ ' and '.join(used_first)+' option we discussed. '
    try:
        when=datetime.fromisoformat(previous.get('date_time',''))
        if when.tzinfo: when=when.astimezone(ZoneInfo('America/Chicago'))
    except (ValueError,TypeError): when=datetime.now(ZoneInfo('America/Chicago'))
    food_status=scheduled_status(food,when);shelter_status=scheduled_status(shelter,when)
    if food_status=='closed': reply+='The food place’s listed hours do not cover that time, so don’t count on a meal there tonight. '
    else: reply+='Please confirm a meal is available at your requested time. '
    if shelter_status=='closed': reply+='The shelter’s listed check-in hours also do not cover that time. '
    elif shelter_status=='open': reply+='The shelter is listed as open then, but a bed is not confirmed. '
    else: reply+='Please confirm the shelter’s check-in time and bed availability. '
    if any(r.get('is_demo') or r.get('availability_is_demo') for r in pair): reply+='Some listing details or bed counts are demo data.'
    return {**base,'reply':reply.strip(),'comparison':{'food_id':food['id'],'shelter_id':shelter['id'],'straight_line_miles':round(miles,2),'food_status_at_requested_time':food_status,'shelter_status_at_requested_time':shelter_status},'map_matches':pair,
            'quick_replies':[{'label':'Find another food place','message':'Find another food place for tonight'}]}
