from decimal import Decimal, InvalidOperation
import random
import csv
from django.urls import reverse
from datetime import date
from datetime import datetime
from django.contrib import messages
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.db.models import Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import get_template
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import UpdateAPIView, ListAPIView, \
    get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from xhtml2pdf import pisa
from django.core.paginator import Paginator
from dashboard.models import AddTailors, Cloth, Customer, Item, Add_order
from .serializers import TailorLoginSerializer, \
    CompletedOrderSerializer, ItemSerializer, InProgressToCompletedSerializer, InProgressOrderSerializer, \
    UpdateToInProgressSerializer, AddOrderSerializer
from django.contrib.auth.decorators import login_required



# Create your views here.
@login_required
def reception_indexpage(request):
    total_customers = Customer.objects.count()
    total_order = Add_order.objects.count()  # Assuming you have an Order model
    total_completed_works = AddTailors.objects.aggregate(Sum('completed_works'))['completed_works__sum']
    cus = Add_order.objects.filter(delivery_date__gte=date.today()).order_by('delivery_date')

    context = {
        'total_customers': total_customers,
        'total_orders': total_order,
        'cus': cus,
        'total_completed_works': total_completed_works
    }
    
    return render(request, 'reception_dashboard.html', context)# Render the default dashboard if admin is logged in



def search_mobile_recption(request):
    results = {'Customer': []}
    query = ""

    if 'q' in request.GET:
        query = request.GET['q']

        results['customer'] = Add_order.objects.select_related('clothdetails', 'customer_id', 'tailor').filter(customer_id__mobile__icontains=query).exclude(customer_id__mobile__isnull=True).exclude(customer_id__mobile__exact='').order_by('-id')

    return render(request, 'search_reception.html', {'results': results, 'query': query})


def customer_details_recption(request):
    cus = Customer.objects.all().order_by('-id')

    # Pagination
    paginator = Paginator(cus, 300)  # Show 300 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "Customer_details_reception.html", {'page_obj': page_obj})


def createcustomer_reception(request):
    tailor = AddTailors.objects.all()
    cloths = Cloth.objects.all()
    tailor_works = []
    for tailor in tailor:
        assigned_works = Add_order.objects.filter(tailor=tailor, status='assigned').count()
        pending_works = Add_order.objects.filter(tailor=tailor,status='in_progress').count()
        tailor_works.append({'tailor': tailor, 'assigned_works': assigned_works, 'pending_works': pending_works})

    context = {'tailor_works': tailor_works,'cloths': cloths}
    return render(request, 'Create_customer_reception.html', context)

def Cloth_details_reception(request):
    query = request.GET.get('q')
    if query:
        cloth = Cloth.objects.filter(name__icontains=query)
    else:
        cloth = Cloth.objects.all()
    return render(request, 'Cloth_details_reception.html', {'cloth':cloth})

def check_tailor_works_recption(request):
    if request.method == 'GET':
        tailor_id = request.GET.get('tailor_id')
        delivery_date = request.GET.get('delivery_date')

        try:
            # Assuming you have a Customer model with a tailor field
            works = Add_order.objects.filter(tailor__id=tailor_id, delivery_date=delivery_date)

            # You may need to serialize the works data based on your requirements
            serialized_works = [{'name': work.name, 'other_field': work.other_field} for work in works]

            return JsonResponse({'works': serialized_works})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=400)


def fetch_tailor_options_recption(request):
    if request.method == 'GET' and 'delivery_date' in request.GET:
        delivery_date = request.GET.get('delivery_date')

        try:
            tailors = AddTailors.objects.all()
            tailor_options = []

            for tailor in tailors:
                try:
                    # Access the related set of Customer objects using customer_set
                    works_on_date = tailor.add_order_set.filter(delivery_date=delivery_date)

                    # Count assigned and pending works separately
                    assigned_works = works_on_date.filter(status='assigned').count()
                    pending_works = works_on_date.filter(status='pending').count()

                    tailor_options.append({
                        'id': tailor.id,
                        'name': tailor.tailor,
                        'assigned_works': assigned_works,
                        'pending_works': pending_works,
                    })
                except Exception as e:
                    print(f"Error processing tailor {tailor.id}: {str(e)}")

            return JsonResponse({'tailor_options': tailor_options})

        except Exception as e:
            # Print the error details to the console
            import traceback
            print(traceback.format_exc())

            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request'}, status=400)


def savecustomer_recption(request):
    context = {}
    if request.method == "POST":
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        center_sleeve = request.POST.get('center_sleeve')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        ds = request.POST.get('other')
        tailor_id = request.POST.get('tailor')
        sb = request.POST.get('sleeve_bottom')
        tp = request.POST.get('total')
        ap = request.POST.get('advance')
        bp = request.POST.get('balance')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id')
        pocket_type = request.POST.get('pocket-type')
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('createcustomer_reception')
        cloth_name = None
        

        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None

        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None  

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None 


        tailor_instance = AddTailors.objects.get(id=tailor_id)

        works_on_delivery_date = Customer.objects.filter(tailor=tailor_instance, delivery_date=dd).count()
        
        cloth = None
        if cloth_id:
            try:
                cloth = Cloth.objects.get(pk=cloth_id)
                cloth_name=cloth.name
                if cloth.stock_length >= ordered_length:
                    cloth.stock_length -= ordered_length
                    cloth.save()
                else:
                    messages.error(request, "Not enough cloth stock available.")
                    return redirect('createcustomer_reception')
            except Cloth.DoesNotExist:
                messages.error(request, "Cloth does not exist.")
                return redirect('createcustomer_reception')
        else:
            ordered_length = None

        tailor_instance.assigned_works += 1
        tailor_instance.save()

        try:
            # Generate a unique bill_number sequentially (format: AA001–ZZ999 = 675,324 max)
            last_bill_number = Add_order.objects.order_by('-bill_number').first()

            if last_bill_number:
                raw = last_bill_number.bill_number
                # Support legacy single-char prefix (e.g. "V285") and new two-char prefix (e.g. "AA001")
                if len(raw) <= 4:
                    prefix = raw[:-3].zfill(1) if len(raw) == 4 else raw[:1]
                    digits = int(raw[-3:])
                else:
                    prefix = raw[:-3]
                    digits = int(raw[-3:])

                if digits < 999:
                    bill_number = f"{prefix}{digits + 1:03d}"
                else:
                    # Increment the prefix: A→B, Z→AA, AA→AB, AZ→BA, ZZ→AAA (practically unreachable)
                    chars = list(prefix)
                    pos = len(chars) - 1
                    while pos >= 0:
                        if chars[pos] < 'Z':
                            chars[pos] = chr(ord(chars[pos]) + 1)
                            break
                        else:
                            chars[pos] = 'A'
                            pos -= 1
                    else:
                        chars = ['A'] + ['A'] * len(chars)  # extend prefix length
                    bill_number = f"{''.join(chars)}001"
            else:
                bill_number = "A001"

            obj = Customer(name=nm, mobile=mn, length=ln, shoulder=sd, loose=lo, regal=rg, 
                            sleeve_sada=sl, sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2,
                           order_date=od, bill_number=bill_number,
                           delivery_date=dd, tailor=tailor_instance, button_type=bt,
                           description=ds,sleeve_bottom=sb,model_details=model_details,
                           cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
                            cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
                            collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve,cloth_name=cloth_name,
                            clothdetails=cloth,ordered_length=ordered_length,pocket_image_url=pocket_image_url,pocket_type=pocket_type
                                      )
            obj.save()

            add_order_obj = Add_order(customer_id=obj, length=ln, shoulder=sd, sleeve_sada=sl,
                                      sleeve_cuff=sll, regal=rg, loose=lo,model_details=model_details,
                                      cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
                                      cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
                                      collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve,
                                       pocket=po, bottom1=b1, seat=b2, button_type=bt,cloth_name=cloth_name,
                                      bill_number=bill_number,total_payment=tp,advance_payment=ap,balance_payment=bp,
                                      order_date=od, delivery_date=dd, tailor=tailor_instance, description=ds,sleeve_bottom=sb,
                                      clothdetails=cloth,ordered_length=ordered_length,pocket_image_url=pocket_image_url,pocket_type=pocket_type)
            add_order_obj.save()

            messages.success(request, "Successfully added customer" , {obj.name})
            return redirect(createcustomer_reception)

        except IntegrityError as e:
            # Handle IntegrityError
            return JsonResponse({'error': f"IntegrityError: {str(e)}"}, status=500)

        except Exception as e:
            # Handle other exceptions
            return JsonResponse({'error': f"Error saving customer: {str(e)}"}, status=500)

    return redirect('customer_details_recption')


def all_customers(request):
    customers = Customer.objects.all()
    return render(request, 'customer_list.html', {'customers': customers})


def single_customer_reception(request, customer_id):
    single = Customer.objects.filter(id=customer_id)
    view_add_order = Add_order.objects.filter(customer_id=customer_id)
    itms = Item.objects.filter(customer_id=customer_id)
    return render(request, "single_customer_reception.html", {'single': single, 'itms': itms, 'view': view_add_order})


def tailor_details_recption(request):
    tailors = AddTailors.objects.all()

    for tailor in tailors:
        # Calculate assigned, pending, upcoming, and completed works
        tailor.assigned_works = Add_order.objects.filter(tailor=tailor, status='assigned').count()
        tailor.pending_works = Add_order.objects.filter(tailor=tailor, status='in_progress').count()
        tailor.upcoming_works = Add_order.objects.filter(tailor=tailor, delivery_date__gt=date.today()).count()
        tailor.completed_works = Add_order.objects.filter(tailor=tailor, status='completed').count()

    context = {'tailors': tailors}
    return render(request, 'View_Tailor_reception.html', context)


# def additems_reception(request, dataid):
#     customers = Customer.objects.get(id=dataid)
#     return render(request, "Add_Items_reception.html", {"customers": customers})


def order_add_item(request, dataid):
    order = Add_order.objects.get(id=dataid)
    return render(request, "Add_Items_reception.html", {'order': order})


def save_items_recption(request):
    if request.method == 'POST':
        order_id = request.POST.get('orderid')

        customer = request.POST.get('customerid')
        item_names = request.POST.getlist('itemName[]')
        quantities = request.POST.getlist('quantity[]')
        prices = request.POST.getlist('price[]')

        order_instance = Add_order.objects.get(id=order_id)
        customer_instance = Customer.objects.get(id=customer)

        for i in range(len(item_names)):
            if i < len(quantities) and i < len(prices):
                item = Item(
                    order_id=order_instance,
                    customer=customer_instance,
                    item_name=item_names[i],
                    item_quantity=int(quantities[i]),
                    item_price=float(prices[i])
                )
                item.save()
            else:
                print(f"Skipping item at index {i} due to incomplete data.")

        return redirect('customer_details_recption')


def order_details_reception(request):
    cus = Add_order.objects.select_related('clothdetails', 'customer_id', 'tailor').all().order_by('-id')
    if request.method == "POST":
        from_date_str = request.POST.get('textfield')
        to_date_str = request.POST.get('textfield2')
        export = request.POST.get('export')

        if from_date_str and to_date_str:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            cus = Add_order.objects.select_related('clothdetails', 'customer_id', 'tailor').filter(delivery_date__range=[from_date, to_date]).order_by('-id')

        if export:  # If export button was clicked, generate the CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="order_details_{from_date_str}_to_{to_date_str}.csv"'

            writer = csv.writer(response)
            writer.writerow(['Order ID', 'Customer ID', 'Name', 'Contact Number', 'Cloth Name', 'Cloth Length', 'Model Details', 'Length', 'Shoulder', 'Sleeve Sada', 'Sleeve Cuff', 'Center Sleeve', 'Sleeve Bottom', 'Loose', 'Seat', 'Regal', 'Collar Type', 'Collar Measurement', 'Cuff Type', 'Cuff Measurements', 'Pocket Type', 'Pocket Measure', 'Button Type', 'Bottom Measure', 'Bill Number', 'Order Date', 'Delivery Date', 'Description', 'Total Price', 'Advance Payment', 'Balance Payment', 'Tailor'])

            for order in cus:
                writer.writerow([
                    order.id, order.customer_id.id, order.customer_id.name, order.customer_id.mobile, 
                    order.clothdetails.name if order.clothdetails else order.cloth_name, 
                    order.ordered_length, order.model_details, order.length, order.shoulder, 
                    order.sleeve_sada, order.sleeve_cuff, order.center_sleeve, order.sleeve_bottom, 
                    order.loose, order.seat, order.regal, order.collar_type, 
                    order.collar_measurements, order.cuff_type, order.cuff_measurements, 
                    order.pocket_type, order.pocket, order.button_type, order.bottom1, 
                    order.bill_number, order.order_date, order.delivery_date, order.description, 
                    order.total_payment, order.advance_payment, order.balance_payment, order.tailor
                ])

            return response
        
    # Pagination
    paginator = Paginator(cus, 300)  # Show 25 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, "Order_Details_reception.html", {'page_obj': page_obj})


def deliver_order_reception(request, order_id):
    if request.method == 'POST':
        order = Add_order.objects.get(pk=order_id)
        order.pending_or_delivered = 'delivered'
        order.save()
        return redirect('reception_indexpage')

def add_order_recption(request, dataid):
    # dataid could be either a Customer ID or an Order ID
    # Try to get as Order first (from search results)
    try:
        order = Add_order.objects.get(id=dataid)
        customer = order.customer_id
        add = order  # Use the specific order's data
    except Add_order.DoesNotExist:
        # If not an order, treat as Customer ID (from customer list)
        customer = Customer.objects.get(id=dataid)
        # Get the most recent order for this customer
        latest_order = Add_order.objects.filter(customer_id=customer).order_by('-id').first()
        if latest_order:
            add = latest_order  # Use latest order's data
        else:
            add = customer  # Use customer's base data

    cloths=Cloth.objects.all()
    # Always pass customer_id separately so the form can save correctly
    return render(request, "Add_order_reception.html", {"add": add, 'cloths':cloths, 'customer': customer, 'customer_id': customer.id})


def edit_order_reception(request, dataid):
    add = Add_order.objects.get(id=dataid)
    cloths=Cloth.objects.all()
    return render(request, "edit_order_reception.html", {"add": add,'cloths':cloths})


def update_add_order_reception(request, dataid):
    if request.method == "POST":
        # Basic field retrieval
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        tailor_id = request.POST.get('tailor')
        other = request.POST.get('other')
        sb = request.POST.get('sleeve_bottom')
        tp = request.POST.get('total')
        ap = request.POST.get('advance')
        bp = request.POST.get('balance')
        center_sleeve = request.POST.get('center_sleeve')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id') or request.POST.get('existing_cloth_id')
        pocket_type = request.POST.get('pocket-type')

        # Handle ordered length safely
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal('3.5')
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('order_details_reception')

        # Handle collar, cuff, and pocket image URLs
        collar_map = {
            'collar1': 'images/collarcuff/collor 1.png',
            'collar2': 'images/collarcuff/collor 2.png',
            'collar3': 'images/collarcuff/collor 3.png',
            'collar4': 'images/collarcuff/collor 4.png',
        }
        pocket_map = {
            'pocket1': 'images/collarcuff/pocket1.png',
            'pocket2': 'images/collarcuff/pocket2.png',
            'pocket3': 'images/collarcuff/pocket3.png',
        }
        cuff_map = {
            'cuff1': 'images/collarcuff/cuff 1.png',
            'cuff2': 'images/collarcuff/cuff 2.png',
            'cuff3': 'images/collarcuff/cuff 3.png',
            'cuff4': 'images/collarcuff/cuff 4.png',
            'cuff5': 'images/collarcuff/cuff 5.png',
        }

        collar_image_url = collar_map.get(collar_type)
        pocket_image_url = pocket_map.get(pocket_type)
        cuff_image_url = cuff_map.get(cuff_type)

        # Get the order and related data
        order = get_object_or_404(Add_order, id=dataid)
        old_tailor = order.tailor
        new_tailor = get_object_or_404(AddTailors, id=tailor_id)

        # --- Update customer details ---
        if order.customer_id:
            customer = order.customer_id
            customer.name = nm
            customer.mobile = mn
            customer.save()

        # --- Cloth stock management ---
        previous_ordered_length = order.ordered_length or Decimal('0')
        ordered_length_decimal = ordered_length or Decimal('0')

        if cloth_id:
            if not order.clothdetails or str(order.clothdetails.id) != cloth_id or previous_ordered_length != ordered_length_decimal:
                length_difference = ordered_length_decimal - previous_ordered_length

                if order.clothdetails and str(order.clothdetails.id) == cloth_id:
                    # Adjust stock for same cloth
                    if ordered_length_decimal < previous_ordered_length:
                        order.clothdetails.stock_length += abs(length_difference)
                    else:
                        if order.clothdetails.stock_length >= length_difference:
                            order.clothdetails.stock_length -= length_difference
                        else:
                            messages.error(request, "Not enough cloth stock available.")
                            return redirect('order_details_reception')
                else:
                    # Handle previous cloth restore
                    if order.clothdetails:
                        prev_cloth = get_object_or_404(Cloth, pk=order.clothdetails.id)
                        prev_cloth.stock_length += previous_ordered_length
                        prev_cloth.save()

                    # Handle new cloth deduction
                    new_cloth = get_object_or_404(Cloth, pk=cloth_id)
                    if new_cloth.stock_length >= ordered_length_decimal:
                        new_cloth.stock_length -= ordered_length_decimal
                        order.clothdetails = new_cloth
                    else:
                        messages.error(request, "Not enough cloth stock available.")
                        return redirect('order_details_reception')

                if order.clothdetails:
                    order.clothdetails.save()
        else:
            # No cloth selected — restore old stock
            if order.clothdetails:
                prev_cloth = get_object_or_404(Cloth, pk=order.clothdetails.id)
                prev_cloth.stock_length += previous_ordered_length
                prev_cloth.save()
            order.clothdetails = None
            ordered_length = None

        cloth_name = order.clothdetails.name if order.clothdetails else None

        # --- Tailor reassignment ---
        # --- Tailor reassignment ---
        if old_tailor != new_tailor:
            if old_tailor:
                old_tailor.assigned_works -= 1
                old_tailor.save()
            new_tailor.assigned_works += 1
            new_tailor.save()

        # --- Order update ---
        Add_order.objects.filter(id=dataid).update(
            length=ln,
            shoulder=sd,
            loose=lo,
            regal=rg,
            sleeve_sada=sl,
            cloth_name=cloth_name,
            sleeve_cuff=sll,
            pocket=po,
            bottom1=b1,
            seat=b2,
            total_payment=tp,
            advance_payment=ap,
            balance_payment=bp,
            order_date=od,
            delivery_date=dd,
            tailor=new_tailor,
            button_type=bt,
            model_details=model_details,
            cuff_measurements=cuff_measurment,
            collar_type_image_url=collar_image_url,
            cuff_type_image_url=cuff_image_url,
            collar_measurements=collar_measurment,
            collar_type=collar_type,
            cuff_type=cuff_type,
            center_sleeve=center_sleeve,
            description=other,
            sleeve_bottom=sb,
            pocket_type=pocket_type,
            ordered_length=ordered_length,
            clothdetails=order.clothdetails,
            pocket_image_url=pocket_image_url
        )

        messages.success(request, "Customer Details Updated Successfully...!")
        return redirect(order_details_reception) 


def save_add_order_recption(request):
    if request.method == "POST":
        id = request.POST.get('id')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        center_sleeve = request.POST.get('center_sleeve')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        tailor_id = request.POST.get('tailor')
        other = request.POST.get('other')
        sb = request.POST.get('sleeve_bottom')
        tp = request.POST.get('total')
        ap = request.POST.get('advance')
        bp = request.POST.get('balance')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id')
        existing_cloth_id = request.POST.get('existing_cloth_id')
        pocket_type = request.POST.get('pocket-type')

        ordered_length_str = request.POST.get('ordered_length', '').strip()
        cloth_name = None

        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None 

        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None 


        tailor_instance = AddTailors.objects.get(id=tailor_id)

        works_on_delivery_date = Add_order.objects.filter(tailor=tailor_instance, delivery_date=dd).count()

        tailor_instance.assigned_works += 1
        tailor_instance.save()
         
        if cloth_id == '':
            cloth_id = None

        if not cloth_id and not existing_cloth_id:
            cloth_id = None

        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('customer_details')

        cloth = None
        if cloth_id:
            try:
                cloth = Cloth.objects.get(pk=cloth_id)
                cloth_name = cloth.name
                if ordered_length and cloth.stock_length >= ordered_length:
                    cloth.stock_length -= ordered_length
                    cloth.save()
                else:
                    messages.error(request, "Not enough cloth stock available.")
                    return redirect('customer_details_recption')
            except Cloth.DoesNotExist:
                messages.error(request, "Cloth does not exist.")
                return redirect('customer_details_recption')
        else:
            ordered_length = None

        # Get or create the tailor instance
        customer_instance = Customer.objects.get(id=id)
        try:
            # Generate a unique bill_number sequentially (format: AA001–ZZ999 = 675,324 max)
            last_bill_number = Add_order.objects.order_by('-bill_number').first()

            if last_bill_number:
                raw = last_bill_number.bill_number
                # Support legacy single-char prefix (e.g. "V285") and new two-char prefix (e.g. "AA001")
                if len(raw) <= 4:
                    prefix = raw[:-3].zfill(1) if len(raw) == 4 else raw[:1]
                    digits = int(raw[-3:])
                else:
                    prefix = raw[:-3]
                    digits = int(raw[-3:])

                if digits < 999:
                    bill_number = f"{prefix}{digits + 1:03d}"
                else:
                    # Increment the prefix: A→B, Z→AA, AA→AB, AZ→BA, ZZ→AAA (practically unreachable)
                    chars = list(prefix)
                    pos = len(chars) - 1
                    while pos >= 0:
                        if chars[pos] < 'Z':
                            chars[pos] = chr(ord(chars[pos]) + 1)
                            break
                        else:
                            chars[pos] = 'A'
                            pos -= 1
                    else:
                        chars = ['A'] + ['A'] * len(chars)  # extend prefix length
                    bill_number = f"{''.join(chars)}001"
            else:
                bill_number = "A001"

            # Create the customer instance
            obj = Add_order(customer_id=customer_instance, length=ln, shoulder=sd, loose=lo,  regal=rg,
                            bill_number=bill_number,sleeve_sada=sl, sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2,
                            order_date=od, total_payment=tp,advance_payment=ap,balance_payment=bp,
                            delivery_date=dd, tailor=tailor_instance, button_type=bt,
                            description=other,sleeve_bottom=sb,model_details=model_details,
                            cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
                            cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
                            collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve
                            ,clothdetails=cloth,ordered_length=ordered_length,cloth_name=cloth_name,
                            pocket_image_url=pocket_image_url,pocket_type=pocket_type)

            obj.save()

            messages.success(request, f"Successfully Added New Order {obj.customer_id.name}")

            return redirect('order_details_reception')
        except IntegrityError as e:
            # Handle IntegrityError
            return JsonResponse({'error': f"IntegrityError: {str(e)}"}, status=500)
        except Exception as e:
            # Handle other exceptions
            return JsonResponse({'error': f"Error saving customer: {str(e)}"}, status=500)

    return redirect('order_details_reception')


def edit_customer_recption(request, dataid):
    ed = AddTailors.objects.all()
    cus = Customer.objects.get(id=dataid)
    cloths=Cloth.objects.all()
    return render(request, "edit_customer_reception.html", {"cus": cus, "ed": ed,'cloths':cloths})


def update_customer_recption(request, dataid):
    if request.method == "POST":
        nm = request.POST.get('name')
        mn = request.POST.get('mobile')
        ln = request.POST.get('length')
        sd = request.POST.get('shoulder')
        sl = request.POST.get('sleeve_sada')
        sll = request.POST.get('sleeve_cuff')
        rg = request.POST.get('regal')
        lo = request.POST.get('loose')
        po = request.POST.get('pocket')
        b1 = request.POST.get('bottom1')
        b2 = request.POST.get('seat')
        od = request.POST.get('order_date')
        dd = request.POST.get('delivery_date')
        bt = request.POST.get('button_type')
        tailor_id = request.POST.get('tailor')
        other = request.POST.get('other')
        sb = request.POST.get('sleeve_bottom')
        center_sleeve = request.POST.get('center_sleeve')
        collar_type = request.POST.get('collar-type')
        cuff_type = request.POST.get('cuff-type')
        cuff_measurment = request.POST.get('cuff-measurements')
        collar_measurment = request.POST.get('collar-measurements')
        model_details = request.POST.get('model_details')
        cloth_id = request.POST.get('cloth_id') or request.POST.get('existing_cloth_id')
        pocket_type = request.POST.get('pocket-type')
        ordered_length_str = request.POST.get('ordered_length', '').strip()
        try:
            if ordered_length_str:
                ordered_length = Decimal(ordered_length_str)
            elif cloth_id:
                ordered_length = Decimal(3.5)
            else:
                ordered_length = None
        except InvalidOperation:
            messages.error(request, "Invalid value for ordered length.")
            return redirect('customer_details_recption')
        cloth_name=None

        if collar_type == 'collar1':
            collar_image_url = 'images/collarcuff/collor 1.png'
        elif collar_type == 'collar2':
            collar_image_url = 'images/collarcuff/collor 2.png'
        elif collar_type == 'collar3':
            collar_image_url = 'images/collarcuff/collor 3.png'
        elif collar_type == 'collar4':
            collar_image_url = 'images/collarcuff/collor 4.png'
        else:
            collar_image_url = None 
        
        if pocket_type == 'pocket1':
            pocket_image_url = 'images/collarcuff/pocket1.png'
        elif pocket_type == 'pocket2':
            pocket_image_url = 'images/collarcuff/pocket2.png'
        elif pocket_type == 'pocket3':
            pocket_image_url = 'images/collarcuff/pocket3.png'
        else:
            pocket_image_url = None 

        if cuff_type == 'cuff1':
            cuff_image_url = 'images/collarcuff/cuff 1.png'
        elif cuff_type == 'cuff2':
            cuff_image_url = 'images/collarcuff/cuff 2.png'
        elif cuff_type == 'cuff3':
            cuff_image_url = 'images/collarcuff/cuff 3.png'
        elif cuff_type == 'cuff4':
            cuff_image_url = 'images/collarcuff/cuff 4.png'
        elif cuff_type == 'cuff5':
            cuff_image_url = 'images/collarcuff/cuff 5.png'
        else:
            cuff_image_url = None 


         # Get the existing customer
        customer = Customer.objects.get(id=dataid)
        cloth=None
        cloth = Cloth.objects.get(pk=cloth_id)
        cloth_name=cloth.name
        # Update the customer instance
        Customer.objects.filter(id=dataid).update(
            name=nm, mobile=mn, length=ln, shoulder=sd, loose=lo,
            regal=rg,sleeve_sada=sl,cloth_name=cloth_name,
            sleeve_cuff=sll, pocket=po, bottom1=b1, seat=b2, button_type=bt,
             description=other,sleeve_bottom=sb,model_details=model_details,
            cuff_measurements=cuff_measurment,collar_type_image_url=collar_image_url,
            cuff_type_image_url=cuff_image_url, collar_measurements=collar_measurment,
            collar_type=collar_type,cuff_type=cuff_type,center_sleeve=center_sleeve,
            clothdetails=cloth_id,ordered_length=ordered_length,pocket_image_url=pocket_image_url,pocket_type=pocket_type
        )
        messages.success(request, "Customer Details Updated Successfully...! ")

    return redirect('customer_details_recption')


def customerdlt_recption(request, dlt):
    delt = Customer.objects.filter(id=dlt)
    delt.delete()
    return redirect(customer_details_recption)


def orderdlt_reception(request, dlt):
    delt = Add_order.objects.filter(id=dlt)
    id = Add_order.objects.get(id=dlt)
    id_dlt = id.tailor.id
    id_cloth=id.clothdetails
    delt.delete()
    tailor_instance = AddTailors.objects.get(id=id_dlt)
    tailor_instance.assigned_works -= 1
    tailor_instance.save()
    if id.ordered_length:
        id_cloth.stock_length += id.ordered_length
        id_cloth.save()
    return redirect(order_details_reception)


def tailor_work_details_recption(request):
    # Retrieve start_date and end_date from the POST request
    start_date_str = request.POST.get('start_date')
    end_date_str = request.POST.get('end_date')

    # Convert start_date_str and end_date_str to datetime objects
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

    # Get all tailors
    tailors = AddTailors.objects.all()

    # Initialize list to store tailor data
    tailor_data = []

    # Iterate through each tailor
    for tailor in tailors:
        # Filter customer orders for the tailor within the date range
        tailor_orders = Add_order.objects.filter(
            tailor=tailor,
            # order_date__gte=start_date,
            delivery_date__lte=end_date,
        )

        # Count the number of orders in each status for the tailor within the date range
        assigned_works = tailor_orders.filter(status='assigned').count()
        pending_works = tailor_orders.filter(status='in_progress').count()
        completed_works = tailor_orders.filter(status='completed').count()

        # Append tailor data to the list
        tailor_data.append({
            'tailor': tailor,
            'assigned_works': assigned_works,
            'pending_works': pending_works,
            'completed_works': completed_works,
        })

    # Pass the results to the template
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'tailor_data': tailor_data,
    }

    return render(request, 'tailor_details_reception.html', context)

    return render(request, 'tailor_work_reception.html')


def select_dates_recption(request):
    return render(request, "tailor_work_reception.html")

def customer_bill_reception(request, customer_id):
    order = get_object_or_404(Add_order.objects.select_related('clothdetails', 'customer_id', 'tailor'), id=customer_id)
    items = Item.objects.filter(order_id=customer_id)
    return render(request, 'Print_measurements_r.html', {'order': order, 'items': items})

def update_print_status_r(request, customer_id):
    if request.method == 'POST':
        order = get_object_or_404(Add_order, id=customer_id)
        if not order.is_printed:
            order.is_printed = True
            order.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'failed'}, status=400)

def print_measurement_reception(request, customer_id):
    customer = Add_order.objects.get(id=customer_id)

    context = {'customer': customer}

    template_path = 'Print_measurements_r.html'
    template = get_template(template_path)
    html = template.render(context)

    # Debugging: Print HcuTML to console
    print(html)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=measurement_{customer_id}.pdf'

    # Create PDF from HTML content
    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', content_type='text/plain')

    return response


# API


class TailorLoginView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = TailorLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        print(f"Attempting to authenticate user: {username}")

        user = authenticate(request, username=username, password=password)

        try:
            user = AddTailors.objects.get(username=username, password=password)
        except AddTailors.DoesNotExist:
            user = None

        if user:
            print(f"Authentication successful for user: {username}")
            refresh = RefreshToken.for_user(user)
            token = str(refresh.access_token)

            response_data = {
                'message': 'Authentication successful',
                'status': True,
                'token': token,
                'user_id': user.id,
                'username': user.username,
            }

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            print(f"Authentication failed for user: {username}")
            response_data = {
                'error': 'Invalid credentials',
                'status': False,
            }
            return Response(response_data, status=status.HTTP_401_UNAUTHORIZED)


class TailorAssignedWorksAPIView(ListAPIView):
    serializer_class = AddOrderSerializer

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        return Add_order.objects.filter(tailor_id=tailor_id, status='assigned')


class AssignedToInProgressAPIView(UpdateAPIView):
    serializer_class = UpdateToInProgressSerializer
    lookup_field = 'id'

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        return Add_order.objects.filter(tailor_id=tailor_id, id=order_id, status='assigned')

    def perform_update(self, serializer):
        # Retrieve the Add_order instance
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        add_order_instance = get_object_or_404(Add_order, tailor_id=tailor_id, id=order_id, status='assigned')

        # Update the status to "in_progress"
        add_order_instance.status = 'in_progress'
        add_order_instance.save()

        # Update other related data or perform additional actions if needed

        # Update the pending works count for the tailor
        tailor_instance = get_object_or_404(AddTailors, id=tailor_id)

        # Decrease the pending works count, but ensure it doesn't go below 0
        if tailor_instance.pending_works > 0:
            tailor_instance.pending_works -= 1
        else:
            # If the pending works count is already 0, do not decrease it further
            tailor_instance.pending_works = 0

        tailor_instance.save()

        # Serialize the updated instance and return the response
        serialized_data = UpdateToInProgressSerializer(add_order_instance).data
        return Response(serialized_data, status=status.HTTP_200_OK)


class InProgressWorksAPIView(ListAPIView):
    serializer_class = InProgressOrderSerializer

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        return Add_order.objects.filter(tailor_id=tailor_id, status='in_progress')


class InProgressToCompletedAPIView(UpdateAPIView):
    serializer_class = InProgressToCompletedSerializer
    lookup_field = 'id'

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        return Add_order.objects.filter(tailor_id=tailor_id, id=order_id, status='in_progress')

    def perform_update(self, serializer):
        # Retrieve the Add_order instance
        tailor_id = self.kwargs['tailor_id']
        order_id = self.kwargs['id']
        add_order_instance = get_object_or_404(Add_order, tailor_id=tailor_id, id=order_id, status='in_progress')

        # Update the status to "completed"
        add_order_instance.status = 'completed'
        add_order_instance.save()

        # Update other related data or perform additional actions if needed

        # Update the pending and completed works count for the tailor
        tailor_instance = get_object_or_404(AddTailors, id=tailor_id)

        # Check for negative values and handle them
        if tailor_instance.pending_works > 0:
            tailor_instance.pending_works -= 1
        else:
            tailor_instance.pending_works = 0

        tailor_instance.completed_works += 1
        tailor_instance.save()

        # Serialize the updated instance and return the response
        serialized_data = InProgressToCompletedSerializer(add_order_instance).data
        return Response(serialized_data, status=status.HTTP_200_OK)


class CompletedOrderListAPIView(ListAPIView):
    serializer_class = CompletedOrderSerializer

    def get_queryset(self):
        tailor_id = self.kwargs['tailor_id']
        return Add_order.objects.filter(tailor_id=tailor_id, status='completed')


class ItemListAPIView(ListAPIView):
    serializer_class = ItemSerializer

    def get_queryset(self):
        order_id = self.kwargs['order_id']
        return Item.objects.filter(order_id=order_id)
